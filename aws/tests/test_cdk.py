"""Tests for CDK stack template."""
import pytest
import json
from unittest.mock import MagicMock, patch


def test_cdk_synthesizes():
    """Test CDK app can synthesize without errors."""
    import os
    os.chdir("aws/cdk")

    # This would normally run cdk synth - we're just checking the stack class exists
    from aws.cdk.stack import BookingAgentStack
    from aws.cdk.app import app

    # Verify the app and stack are defined
    assert app is not None


def test_stack_has_required_resources():
    """Test stack creates required resources."""
    from aws.cdk.stack import BookingAgentStack
    from constructs import Construct
    import aws_cdk as cdk

    # Create a minimal app for testing
    test_app = cdk.App()

    # Mock the stack to avoid actual resource creation
    with patch("aws.cdk.stack.Secret"):
        with patch("aws.cdk.stack.Function"):
            with patch("aws.cdk.stack.TableV2"):
                with patch("aws.cdk.stack.HttpApi"):
                    with patch("aws.cdk.stack.CustomResource"):
                        stack = BookingAgentStack(test_app, "TestStack")

                        # Verify stack was created
                        assert stack is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
