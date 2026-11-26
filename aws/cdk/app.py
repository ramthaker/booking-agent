#!/usr/bin/env python3
"""CDK entry point for WhatsApp Booking Agent."""
import os
import sys

# Fix for relative imports - convert to absolute imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aws_cdk as cdk
from aws.cdk.stack import BookingAgentStack

app = cdk.App()
BookingAgentStack(app, "BookingAgentStack", env=cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "ap-south-1"),
))
app.synth()
