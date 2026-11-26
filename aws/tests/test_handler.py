"""Tests for Lambda handler."""
import pytest
import json
from unittest.mock import patch, MagicMock


def test_verification_challenge_success():
    """Test GET verification returns challenge."""
    from aws.lambda.whatsapp_handler.handler import lambda_handler

    event = {
        "httpMethod": "GET",
        "queryStringParameters": {
            "hub.mode": "subscribe",
            "hub.verify_token": "my_verify_token",
            "hub.challenge": "test_challenge_123"
        }
    }

    with patch.dict("os.environ", {"META_VERIFY_TOKEN": "my_verify_token"}):
        response = lambda_handler(event, {})

        assert response["statusCode"] == 200
        assert response["body"] == "test_challenge_123"


def test_verification_challenge_wrong_token():
    """Test GET verification rejects wrong token."""
    from aws.lambda.whatsapp_handler.handler import lambda_handler

    event = {
        "httpMethod": "GET",
        "queryStringParameters": {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "test_challenge"
        }
    }

    with patch.dict("os.environ", {"META_VERIFY_TOKEN": "my_verify_token"}):
        response = lambda_handler(event, {})

        assert response["statusCode"] == 403


def test_inbound_message_valid():
    """Test POST with valid message processes correctly."""
    from aws.lambda.whatsapp_handler.handler import lambda_handler

    # Valid Meta webhook payload
    body = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "1234567890",
                        "id": "wamid.123",
                        "type": "text",
                        "text": {"body": "Book Dr Rao"}
                    }]
                }
            }]
        }]
    }

    event = {
        "httpMethod": "POST",
        "body": json.dumps(body),
        "headers": {
            "x-hub-signature-256": "sha256=test"  # Will be mocked
        }
    }

    with patch("aws.lambda.whatsapp_handler.handler.verify_signature", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.parse_inbound", return_value={
             "from": "1234567890", "message_id": "wamid.123", "text": "Book Dr Rao"
         }), \
         patch("aws.lambda.whatsapp_handler.handler.check_rate", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.invoke_agent", return_value="I found slots"), \
         patch("aws.lambda.whatsapp_handler.handler.send_reply", return_value=True):

        response = lambda_handler(event, {})

        assert response["statusCode"] == 200


def test_inbound_message_rate_limited():
    """Test POST with rate limited message returns 200 with reply sent."""
    from aws.lambda.whatsapp_handler.handler import lambda_handler

    body = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "1234567890",
                        "id": "wamid.123",
                        "type": "text",
                        "text": {"body": "Test"}
                    }]
                }
            }]
        }]
    }

    event = {
        "httpMethod": "POST",
        "body": json.dumps(body),
        "headers": {
            "x-hub-signature-256": "sha256=test"
        }
    }

    with patch("aws.lambda.whatsapp_handler.handler.verify_signature", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.parse_inbound", return_value={
             "from": "1234567890", "message_id": "wamid.123", "text": "Test"
         }), \
         patch("aws.lambda.whatsapp_handler.handler.check_rate", return_value=False), \
         patch("aws.lambda.whatsapp_handler.handler.send_reply") as mock_send:

        response = lambda_handler(event, {})

        assert response["statusCode"] == 200
        mock_send.assert_called_once()
        assert "too many requests" in mock_send.call_args[0][1].lower()


def test_status_update_ignored():
    """Test status update webhooks return 200 without processing."""
    from aws.lambda.whatsapp_handler.handler import lambda_handler

    # Status update (no messages array)
    body = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{
                        "id": "wamid.123",
                        "status": "delivered"
                    }]
                }
            }]
        }]
    }

    event = {
        "httpMethod": "POST",
        "body": json.dumps(body),
        "headers": {
            "x-hub-signature-256": "sha256=test"
        }
    }

    with patch("aws.lambda.whatsapp_handler.handler.verify_signature", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.parse_inbound", return_value=None):

        response = lambda_handler(event, {})

        assert response["statusCode"] == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
