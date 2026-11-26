# Requirements Document

## Introduction

This feature deploys the Demo 1 appointment-booking concierge from the existing local workshop to AWS. The local deterministic simulator (`agent_workshop/booking.py`) is replaced by real Amazon Bedrock agents using the Strands SDK agent-as-tool pattern, with an AgentCore Runtime or Harness execution environment. Infrastructure is defined in a CDK Python stack that provisions API Gateway, Lambda, S3, and DynamoDB. The web UI continues to serve the same booking and race-condition demonstrations, but agent responses are now produced by real foundation-model reasoning visible to the audience. All data remains synthetic; no real patients, clinicians, SMS numbers, or scheduling systems are involved. Workshop safety constraints from the existing README are preserved throughout.

## Glossary

- **CDK Stack**: The AWS CDK (Python) application that defines and deploys all infrastructure resources for this feature.
- **Supervisor Agent**: The Strands `Agent` instance that receives inbound chat requests and delegates to specialist agents using the agent-as-tool pattern.
- **Availability Specialist**: The Strands `Agent` instance invoked as a tool by the Supervisor Agent; it reads the synthetic slot catalogue from DynamoDB and returns available appointments.
- **Booking Lambda**: The AWS Lambda function that handles `/chat` and `/booking/race` API requests, instantiates Strands agents, and writes booking records to DynamoDB.
- **DynamoDB Table**: The single Amazon DynamoDB table that stores synthetic appointment slots, conversation state, booking records, and idempotency records.
- **API Gateway**: The Amazon API Gateway REST API that exposes `/chat` and `/booking/race` endpoints to the web UI.
- **S3 Bucket**: The Amazon S3 bucket configured as a static website origin that serves `web/index.html` to workshop attendees.
- **AgentCore Runtime**: The Amazon Bedrock AgentCore managed execution environment that runs Strands agents.
- **AgentCore Harness**: The Amazon Bedrock AgentCore Harness, an alternative managed execution mode with built-in defaults, tools, and lifecycle hooks.
- **Conditional Write**: A DynamoDB `PutItem` operation with a `attribute_not_exists` condition expression that atomically rejects a duplicate slot booking.
- **Idempotency Record**: A DynamoDB item keyed on `message_id` that stores the serialised `BookingReply` for a previously processed message, enabling exactly-once delivery semantics.
- **Race Demo**: The endpoint and test that fires 20 concurrent booking confirmations for the same slot and asserts exactly 1 `CONFIRMED` and 19 `CONFLICT` outcomes.
- **BEDROCK_MODEL_ID**: The environment variable that specifies the Amazon Bedrock model identifier used by both Strands agents.
- **Synthetic Data**: Fictional clinicians, patients, slot times, and customer identifiers used exclusively for demonstration purposes.
- **Workshop Safety Constraints**: The boundaries stated in the project README: no real SMS, no real patient data, no real clinic, no production credentials on stage, no Internet-facing server without authentication.

## Requirements

### Requirement 1: CDK Stack Provisioning

**User Story:** As a workshop presenter, I want a single CDK deploy command to create all required AWS resources, so that I can stand up the demo environment without manual console steps.

#### Acceptance Criteria

1. THE CDK Stack SHALL define a DynamoDB table, an S3 bucket, an API Gateway REST API, and a Booking Lambda as CloudFormation resources.
2. THE CDK Stack SHALL pass `BEDROCK_MODEL_ID`, `AWS_REGION`, `DYNAMODB_TABLE_NAME`, and `AGENTCORE_RUNTIME_ARN` as environment variables to the Booking Lambda.
3. WHEN the CDK Stack is synthesised, THE CDK Stack SHALL produce a CloudFormation template with no unresolved `Fn::ImportValue` references to resources outside the stack.
4. THE CDK Stack SHALL grant the Booking Lambda an IAM role with least-privilege policies: `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Query`, and `bedrock:InvokeModel` for the configured model ARN only.
5. THE CDK Stack SHALL configure the S3 bucket with `BlockPublicAcls` and `BlockPublicPolicy` set to `true` and serve the static site through a CloudFront distribution or an S3 website endpoint restricted to the VPC, in accordance with workshop safety constraints.
6. WHERE a `DEPLOY_STAGE` environment variable is set to `prod`, THE CDK Stack SHALL enable DynamoDB point-in-time recovery on the booking table.

### Requirement 2: DynamoDB Table Schema and Slot Seeding

**User Story:** As a developer, I want a DynamoDB table that faithfully replaces the SQLite schema, so that all booking invariants and idempotency guarantees are preserved.

#### Acceptance Criteria

1. THE DynamoDB Table SHALL use `pk` (String, partition key) and `sk` (String, sort key) as the primary key, with entity types distinguished by `pk` prefix (`SLOT#`, `BOOKING#`, `CONV#`, `MSG#`, `ESCALATION#`).
2. WHEN the CDK Stack is deployed for the first time, THE CDK Stack SHALL seed the DynamoDB Table with the three synthetic appointment slots: `SLOT#R-1730` (Dr Rao, West Clinic, 2026-12-04 17:30), `SLOT#R-1800` (Dr Rao, West Clinic, 2026-12-04 18:00), and `SLOT#S-1600` (Dr Shah, East Clinic, 2026-12-04 16:00).
3. WHEN the Booking Lambda attempts to confirm a slot, THE Booking Lambda SHALL execute a DynamoDB `PutItem` with a `attribute_not_exists(pk)` condition expression on the `BOOKING#{slot_id}` item so that only the first writer succeeds.
4. WHEN the DynamoDB Conditional Write fails with `ConditionalCheckFailedException`, THE Booking Lambda SHALL return a `BookingReply` with `state` equal to `CONFLICT` without creating a booking record.
5. WHEN the Booking Lambda receives a request whose `message_id` already exists in the DynamoDB Table as a `MSG#{message_id}` item, THE Booking Lambda SHALL return the stored `response_json` without invoking the Supervisor Agent.

### Requirement 3: Strands Multi-Agent Implementation

**User Story:** As a workshop presenter, I want real foundation-model reasoning visible in agent responses, so that the audience can observe live Strands agent-as-tool orchestration instead of canned text.

#### Acceptance Criteria

1. THE Booking Lambda SHALL instantiate a Supervisor Agent using the Strands `Agent` class with the `BedrockModel` provider configured from `BEDROCK_MODEL_ID` and `AWS_REGION`.
2. THE Booking Lambda SHALL instantiate an Availability Specialist as a Strands `Agent` decorated as a `@tool`, registered in the Supervisor Agent's `tools` list, following the agent-as-tool pattern documented at `https://strandsagents.com/docs/learning/multi-agent-patterns-agents-as-tools/`.
3. THE Availability Specialist SHALL be restricted to read-only DynamoDB operations (`dynamodb:GetItem`, `dynamodb:Query`) and SHALL NOT perform `PutItem` or `DeleteItem`.
4. THE Supervisor Agent system prompt SHALL instruct the agent that it must never claim to have committed a booking; only the Booking Lambda's authoritative DynamoDB write constitutes a confirmed booking.
5. WHEN the Supervisor Agent produces a response, THE Booking Lambda SHALL extract the agent's reasoning text and populate the `message` field of the `BookingReply` with that text rather than a static template string.
6. WHERE `AGENTCORE_RUNTIME_ARN` is set, THE Booking Lambda SHALL invoke the Supervisor Agent via AgentCore Runtime; WHERE `AGENTCORE_RUNTIME_ARN` is not set, THE Booking Lambda SHALL invoke the Supervisor Agent directly via the Strands SDK.

### Requirement 4: API Gateway Endpoints

**User Story:** As the web UI, I want `/chat` and `/booking/race` REST endpoints, so that the browser can send booking messages and trigger the race-condition demonstration.

#### Acceptance Criteria

1. THE API Gateway SHALL expose a `POST /chat` resource that accepts `{"customer": string, "text": string, "message_id": string}` and returns a `BookingReply` JSON object.
2. THE API Gateway SHALL expose a `POST /booking/race` resource that accepts an empty body or `{}` and returns `{"contenders": integer, "confirmed": integer, "conflicts": integer, "booking_rows": integer}`.
3. WHEN a request body exceeds 8192 bytes, THE API Gateway SHALL return HTTP 413 before forwarding the request to the Booking Lambda.
4. WHEN the `customer` field exceeds 100 characters, the `text` field exceeds 2000 characters, or the `message_id` field exceeds 128 characters, THE Booking Lambda SHALL return HTTP 400 with an `{"error": string}` body.
5. THE API Gateway SHALL enable CORS for the S3 static site origin by returning `Access-Control-Allow-Origin` and `Access-Control-Allow-Methods` headers on all responses.
6. IF the Booking Lambda returns an unhandled exception, THEN THE API Gateway SHALL return HTTP 500 with `{"error": "Demo operation failed"}` and SHALL NOT expose internal stack traces in the response body.

### Requirement 5: S3 Static Site and Web UI

**User Story:** As a workshop attendee, I want the same browser UI served from S3, so that I can interact with the live AWS-backed booking demo without installing anything locally.

#### Acceptance Criteria

1. THE CDK Stack SHALL upload `web/index.html` as an S3 object with content type `text/html; charset=utf-8` and configure the S3 bucket to serve it as the index document.
2. WHEN the web UI sends a message to `POST /chat`, THE web UI SHALL display the `agent`, `state`, and `message` fields from the `BookingReply` response in the conversation panel, showing real agent reasoning text.
3. WHEN the web UI receives a `BookingReply` with `state` equal to `CONFIRMED`, THE web UI SHALL display the `reference` field as the booking confirmation number.
4. WHEN the web UI receives a `BookingReply` with `state` equal to `CONFLICT`, THE web UI SHALL display a conflict notice without a reference number.
5. THE web UI SHALL update the `api/metrics`-equivalent endpoint after each chat message to reflect the current DynamoDB slot availability.
6. THE web UI index.html SHALL retain the disclaimer: "Educational fixture · No phone number provisioned · No live clinic · AWS demo deployment."

### Requirement 6: Race Condition Demonstration

**User Story:** As a workshop presenter, I want the 20-customer race-condition endpoint to produce exactly 1 confirmed booking and 19 conflicts every time, so that the audience can observe DynamoDB conditional writes as the correctness mechanism.

#### Acceptance Criteria

1. WHEN `POST /booking/race` is received, THE Booking Lambda SHALL pre-populate 20 synthetic conversation records in DynamoDB, each offering slot `R-1730` to a distinct `race-customer-{n}` identity.
2. WHEN `POST /booking/race` is received, THE Booking Lambda SHALL send 20 concurrent `YES` confirmation messages using `concurrent.futures.ThreadPoolExecutor` with `max_workers` equal to 20.
3. WHEN the race completes, THE Booking Lambda SHALL return `{"contenders": 20, "confirmed": 1, "conflicts": 19, "booking_rows": 1}` as an invariant, not a measured throughput benchmark.
4. IF the `confirmed` count returned from the race is not equal to 1, THEN THE Booking Lambda SHALL log the actual counts at ERROR level and return HTTP 500.
5. THE race demonstration SHALL use only the synthetic `race-customer-{n}` identities and SHALL NOT affect conversation state for non-race customers in the same DynamoDB Table.

### Requirement 7: Environment Variable Configuration

**User Story:** As a developer, I want all runtime parameters driven by environment variables, so that I can reconfigure the deployment for different AWS regions or models without code changes.

#### Acceptance Criteria

1. THE Booking Lambda SHALL read `BEDROCK_MODEL_ID` to select the Amazon Bedrock foundation model; IF `BEDROCK_MODEL_ID` is not set, THEN THE Booking Lambda SHALL raise a startup error and log `"BEDROCK_MODEL_ID is required"`.
2. THE Booking Lambda SHALL read `AWS_REGION` to configure the Boto3 session; IF `AWS_REGION` is not set, THEN THE Booking Lambda SHALL default to the Lambda execution environment's `AWS_DEFAULT_REGION`.
3. THE Booking Lambda SHALL read `DYNAMODB_TABLE_NAME` to identify the DynamoDB table; IF `DYNAMODB_TABLE_NAME` is not set, THEN THE Booking Lambda SHALL raise a startup error and log `"DYNAMODB_TABLE_NAME is required"`.
4. THE Booking Lambda SHALL read `AGENTCORE_RUNTIME_ARN` to select the AgentCore execution path; IF `AGENTCORE_RUNTIME_ARN` is not set, THE Booking Lambda SHALL fall back to direct Strands SDK invocation.
5. THE CDK Stack SHALL read the deployment-time `BEDROCK_MODEL_ID` environment variable from the CDK execution context and pass it to the Lambda environment; IF the variable is absent at synth time, THE CDK Stack SHALL fail with a descriptive error message.

### Requirement 8: Workshop Safety Constraints

**User Story:** As a workshop organiser, I want all README safety constraints enforced at the infrastructure and code level, so that no real patient data, SMS traffic, or production systems are reachable from the demo.

#### Acceptance Criteria

1. THE Booking Lambda SHALL use only Synthetic Data for slot identifiers, clinician names, customer identifiers, and appointment times; THE Booking Lambda SHALL NOT accept or store free-text fields that exceed demo input limits.
2. THE CDK Stack SHALL NOT provision any AWS End User Messaging SMS, Amazon Connect, or SNS-to-external-number resources.
3. WHEN the Booking Lambda receives a message containing urgent wording (`urgent`, `chest pain`), THE Booking Lambda SHALL return an escalation reply including the text `"For a medical emergency, contact local emergency services immediately."` without routing the message to a Strands agent.
4. THE API Gateway SHALL NOT expose endpoints other than `POST /chat`, `POST /booking/race`, and `GET /metrics`.
5. THE S3 bucket SHALL block all public access and serve content only through the designated distribution or VPC endpoint, in accordance with workshop safety constraints.
6. THE CDK Stack README section SHALL document that real patient information, production credentials, and real clinic scheduling systems must never be used with this deployment.

### Requirement 9: README Documentation

**User Story:** As a workshop presenter, I want the project README updated with an AWS deployment section, so that I can follow a clear sequence of steps to go from local demo to live AWS demo.

#### Acceptance Criteria

1. THE README SHALL include an `## AWS Deployment` section that documents the prerequisites: Python 3.10+, AWS CDK v2, an AWS account with Bedrock model access enabled, and the `strands-agents` package.
2. THE README SHALL document the exact sequence of commands: set environment variables, `cdk bootstrap`, `cdk deploy`, and the URL output location for the S3 static site.
3. THE README SHALL state that the AWS deployment uses Synthetic Data only and that no real patients, clinicians, or SMS numbers are provisioned.
4. THE README SHALL list the required IAM permissions a deployer needs: `cloudformation:*`, `iam:CreateRole`, `iam:AttachRolePolicy`, `lambda:*`, `dynamodb:*`, `s3:*`, `apigateway:*`, and `bedrock:InvokeModel`.
5. THE README SHALL retain all existing local-demo instructions unchanged so that the workshop can still be run offline without AWS credentials.
