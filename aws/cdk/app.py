#!/usr/bin/env python3
"""CDK entry point for WhatsApp Booking Agent."""
import os
import sys

# Ensure parent directory is in path for relative imports to work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aws_cdk as cdk

# Import stack using relative path
from stack import BookingAgentStack

app = cdk.App()
stack_name = os.getenv("CDK_STACK_NAME", "BookingAgentStackUsEast")
BookingAgentStack(app, stack_name, env=cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
))
app.synth()
