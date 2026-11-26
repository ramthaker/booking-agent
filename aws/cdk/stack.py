"""CDK stack for WhatsApp Booking Agent."""
from __future__ import annotations

import os
import sys
from typing import Any

import aws_cdk as cdk
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_secretsmanager as secrets
import aws_cdk.aws_apigateway as apigateway
from constructs import Construct


class BookingAgentStack(cdk.Stack):
    """CDK stack for the WhatsApp Booking Agent."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ===== 0. AgentCore Harness (Managed Agent) =====
        # Note: AgentCore Harness is created via AWS Console or CloudFormation
        # We reference it here via env var AGENTCORE_HARNESS_ARN
        # Create a harness at: https://console.aws.amazon.com/bedrock/home?region=ap-south-1#/agent-harnesses
        # Or use CloudFormation with AWS::Bedrock::Agent
        harness_arn = os.getenv("AGENTCORE_HARNESS_ARN", "")

        # ===== 1. DynamoDB Table =====
        table = dynamodb.TableV2(
            self,
            "BookingTable",
            partition_key=dynamodb.Attribute(
                name="pk", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="sk", type=dynamodb.AttributeType.STRING
            ),
            billing=dynamodb.Billing.on_demand(),  # Pay-per-request
            deletion_protection=False,  # Enable in production
            point_in_time_recovery=True,
        )

        # Add TTL attribute
        table.add_global_secondary_index(
            index_name="ttl-index",
            partition_key=dynamodb.Attribute(
                name="ttl", type=dynamodb.AttributeType.NUMBER
            ),
            sort_key=dynamodb.Attribute(
                name="pk", type=dynamodb.AttributeType.STRING
            ),
        )

        # ===== 2. Secrets Manager =====
        meta_secret = secrets.Secret(
            self,
            "MetaCredentials",
            secret_name="WhatsApp/MetaCredentials",
            description="Meta WhatsApp Business credentials",
            generate_secret_string=secrets.SecretStringGenerator(
                exclude_punctuation=True,
            ),
        )

        # ===== 3. Lambda Function =====
        lambda_role = iam.Role(
            self,
            "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "DynamoDBAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "dynamodb:GetItem",
                                "dynamodb:PutItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:DeleteItem",
                                "dynamodb:Query",
                                "dynamodb:Scan",
                            ],
                            resources=[table.table_arn],
                        ),
                    ]
                ),
                "BedrockAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                                f"arn:aws:bedrock:{self.region}::foundation-model/amazon.nova-lite-v1:0",
                                f"arn:aws:bedrock:{self.region}::foundation-model/amazon.nova-pro-v1:0",
                            ],
                        ),
                    ]
                ),
                "AgentCoreAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "bedrock-agentcore:InvokeAgentRuntime",
                                "bedrock-agentcore:PutMemory",
                                "bedrock-agentcore:GetMemory",
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}:{self.account}:agent-runtime/*"
                            ],
                        ),
                    ]
                ),
                "SecretsAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["secretsmanager:GetSecretValue"],
                            resources=[meta_secret.secret_arn],
                        ),
                    ]
                ),
            },
        )

        lambda_function = lambda_.Function(
            self,
            "WhatsAppHandler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(
                "../lambda/whatsapp_handler",
                exclude=["*.pyc", "__pycache__", "*.pyo"],
            ),
            role=lambda_role,
            timeout=cdk.Duration.seconds(30),
            memory_size=512,
            environment={
                "DYNAMODB_TABLE_NAME": table.table_name,
                "BEDROCK_MODEL_ID": os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"),
                "REGION": self.region,  # Use REGION instead of AWS_REGION (reserved by Lambda)
                "RATE_LIMIT_PER_MINUTE": "5",
                "AGENT_MODE": os.getenv("AGENT_MODE", "lambda-strands"),  # lambda-strands, agentcore-runtime, agentcore-harness
                "AGENTCORE_HARNESS_ARN": harness_arn,  # Required for agentcore-runtime and agentcore-harness
                "META_VERIFY_TOKEN": meta_secret.secret_value_from_json("verify_token").unsafe_unwrap(),
                "META_ACCESS_TOKEN": meta_secret.secret_value_from_json("access_token").unsafe_unwrap(),
                "META_APP_SECRET": meta_secret.secret_value_from_json("app_secret").unsafe_unwrap(),
                "META_PHONE_NUMBER_ID": meta_secret.secret_value_from_json("phone_number_id").unsafe_unwrap(),
            },
        )

        # ===== 4. API Gateway (REST API for Lambda proxy integration) =====
        api = apigateway.RestApi(
            self,
            "WhatsAppApi",
            rest_api_name="WhatsApp Booking Agent API",
            description="API for WhatsApp booking agent",
            cloud_watch_role=True,
        )

        api_root = api.root.add_resource("{proxy}")
        api_root.add_method(
            "ANY",
            apigateway.LambdaIntegration(lambda_function),
            authorization_type=apigateway.AuthorizationType.NONE,
        )

        # ===== 5. Seed Lambda (Custom Resource) =====
        seed_lambda_role = iam.Role(
            self,
            "SeedLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "SeedAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "dynamodb:GetItem",
                                "dynamodb:PutItem",
                            ],
                            resources=[table.table_arn],
                        ),
                    ]
                ),
            },
        )

        seed_lambda = lambda_.Function(
            self,
            "SeedSlots",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="seed.handler",
            code=lambda_.Code.from_inline("""
import boto3
import os
from botocore.exceptions import ClientError

def handler(event, context):
    if event.get('RequestType') not in ['Create', 'Update']:
        return {'PhysicalResourceId': event.get('PhysicalResourceId', 'seed')}
    
    table_name = os.getenv('DYNAMODB_TABLE_NAME')
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    # Seed slots
    slots = [
        {'pk': 'SLOT#R-1730', 'sk': 'SLOT', 'doctor': 'Dr Rao', 'clinic': 'West Clinic', 'time': '2026-12-04 17:30', 'available': True},
        {'pk': 'SLOT#R-1800', 'sk': 'SLOT', 'doctor': 'Dr Rao', 'clinic': 'West Clinic', 'time': '2026-12-04 18:00', 'available': True},
        {'pk': 'SLOT#S-1600', 'sk': 'SLOT', 'doctor': 'Dr Shah', 'clinic': 'East Clinic', 'time': '2026-12-04 16:00', 'available': True},
    ]
    
    for slot in slots:
        table.put_item(Item=slot, ConditionExpression='attribute_not_exists(pk)')
    
    return {'PhysicalResourceId': 'seed'}
"""),
            role=seed_lambda_role,
            timeout=cdk.Duration.seconds(10),
            memory_size=128,
            environment={
                "DYNAMODB_TABLE_NAME": table.table_name,
            },
        )

        cdk.CustomResource(
            self,
            "SeedSlotsResource",
            service_token=seed_lambda.function_arn,
            properties={"TableArn": table.table_arn},
        )

        # ===== Outputs =====
        cdk.CfnOutput(
            self,
            "ApiEndpoint",
            value=api.url.rstrip("/"),
            description="API Gateway endpoint URL",
        )
        cdk.CfnOutput(
            self,
            "TableName",
            value=table.table_name,
            description="DynamoDB table name",
        )
        cdk.CfnOutput(
            self,
            "SecretArn",
            value=meta_secret.secret_arn,
            description="Secrets Manager secret ARN",
        )
