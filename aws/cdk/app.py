#!/usr/bin/env python3
"""CDK entry point for WhatsApp Booking Agent."""
import os
import aws_cdk as cdk
from .stack import BookingAgentStack

app = cdk.App()
BookingAgentStack(app, "BookingAgentStack", env=cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "ap-south-1"),
))
app.synth()
