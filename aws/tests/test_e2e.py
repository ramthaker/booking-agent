"""End-to-end test for WhatsApp Booking Agent without AWS."""
import pytest
import json
import hashlib
from unittest.mock import patch, MagicMock


def test_e2e_booking_flow():
    """Test complete booking flow from WhatsApp message to reply."""
    from aws.lambda.whatsapp_handler.handler import lambda_handler

    # Simulated Meta webhook payload
    body = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "215589313241560883",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{
                        "profile": {"name": "Priya"},
                        "wa_id": "1234567890"
                    }],
                    "messages": [{
                        "from": "1234567890",
                        "id": "wamid.123",
                        "type": "text",
                        "text": {"body": "What slots are available?"}
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    # Mock all external dependencies
    with patch("aws.lambda.whatsapp_handler.handler.verify_signature", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.parse_inbound") as mock_parse, \
         patch("aws.lambda.whatsapp_handler.handler.check_rate", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.invoke_agent") as mock_invoke, \
         patch("aws.lambda.whatsapp_handler.handler.send_reply") as mock_send:

        # Setup mocks
        mock_parse.return_value = {
            "from": "1234567890",
            "message_id": "wamid.123",
            "text": "What slots are available?"
        }
        mock_invoke.return_value = "Available slots:\n- Dr Rao at West Clinic on 2026-12-04 (17:30)\n- Dr Rao at West Clinic on 2026-12-04 (18:00)"

        # Build event
        event = {
            "httpMethod": "POST",
            "body": json.dumps(body),
            "headers": {
                "x-hub-signature-256": "sha256=test"
            }
        }

        # Call handler
        response = lambda_handler(event, {})

        # Verify response
        assert response["statusCode"] == 200

        # Verify agent was invoked with correct session ID
        mock_invoke.assert_called_once()
        call_args = mock_invoke.call_args
        session_id = call_args[1]["session_id"]
        phone_hash = hashlib.sha256("1234567890".encode()).hexdigest()
        assert session_id == phone_hash

        # Verify reply was sent
        mock_send.assert_called_once()
        reply_args = mock_send.call_args
        assert reply_args[0][0] == "1234567890"
        assert "slots" in reply_args[0][1].lower()


def test_e2e_booking_flow_second_turn():
    """Test second turn of conversation - booking confirmation."""
    from aws.lambda.whatsapp_handler.handler import lambda_handler

    body = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"wa_id": "1234567890"}],
                    "messages": [{
                        "from": "1234567890",
                        "id": "wamid.456",
                        "type": "text",
                        "text": {"body": "YES I want to book"}
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    with patch("aws.lambda.whatsapp_handler.handler.verify_signature", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.parse_inbound") as mock_parse, \
         patch("aws.lambda.whatsapp_handler.handler.check_rate", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.invoke_agent") as mock_invoke, \
         patch("aws.lambda.whatsapp_handler.handler.send_reply") as mock_send:

        mock_parse.return_value = {
            "from": "1234567890",
            "message_id": "wamid.456",
            "text": "YES I want to book"
        }
        mock_invoke.return_value = "Confirmed! Appointment BK-ABC12345 with Dr Rao at West Clinic on 2026-12-04 at 17:30."

        event = {
            "httpMethod": "POST",
            "body": json.dumps(body),
            "headers": {"x-hub-signature-256": "sha256=test"}
        }

        response = lambda_handler(event, {})

        assert response["statusCode"] == 200
        mock_invoke.assert_called_once()


def test_e2e_rate_limiting():
    """Test that rate limiting returns appropriate reply."""
    from aws.lambda.whatsapp_handler.handler import lambda_handler

    body = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "messages": [{
                        "from": "1234567890",
                        "type": "text",
                        "text": {"body": "Rate limit test"}
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    with patch("aws.lambda.whatsapp_handler.handler.verify_signature", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.parse_inbound") as mock_parse, \
         patch("aws.lambda.whatsapp_handler.handler.check_rate", return_value=False), \
         patch("aws.lambda.whatsapp_handler.handler.send_reply") as mock_send:

        mock_parse.return_value = {
            "from": "1234567890",
            "message_id": "wamid.789",
            "text": "Rate limit test"
        }

        event = {
            "httpMethod": "POST",
            "body": json.dumps(body),
            "headers": {"x-hub-signature-256": "sha256=test"}
        }

        response = lambda_handler(event, {})

        assert response["statusCode"] == 200

        # Verify rate limit message was sent
        mock_send.assert_called_once()
        reply_text = mock_send.call_args[0][1]
        assert "too many requests" in reply_text.lower() or "wait" in reply_text.lower()


def test_e2e_booking_confirmation_message():
    """Test the full booking confirmation flow."""
    from aws.lambda.whatsapp_handler.handler import lambda_handler

    # First turn - check availability
    availability_body = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "9876543210",
                        "type": "text",
                        "text": {"body": "Book Dr Rao Friday 5 PM"}
                    }]
                }
            }]
        }]
    }

    # Second turn - confirmation
    confirm_body = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "9876543210",
                        "type": "text",
                        "text": {"body": "YES"}
                    }]
                }
            }]
        }]
    }

    with patch("aws.lambda.whatsapp_handler.handler.verify_signature", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.parse_inbound") as mock_parse, \
         patch("aws.lambda.whatsapp_handler.handler.check_rate", return_value=True), \
         patch("aws.lambda.whatsapp_handler.handler.invoke_agent") as mock_invoke, \
         patch("aws.lambda.whatsapp_handler.handler.send_reply") as mock_send:

        # First call - availability check
        mock_parse.return_value = {
            "from": "9876543210",
            "message_id": "wamid.first",
            "text": "Book Dr Rao Friday 5 PM"
        }
        mock_invoke.return_value = "I found Dr Rao at West Clinic on 2026-12-04 at 17:30. Reply YES to confirm."

        event1 = {
            "httpMethod": "POST",
            "body": json.dumps(availability_body),
            "headers": {"x-hub-signature-256": "sha256=test"}
        }

        response1 = lambda_handler(event1, {})
        assert response1["statusCode"] == 200

        # Second call - confirmation
        mock_parse.return_value = {
            "from": "9876543210",
            "message_id": "wamid.second",
            "text": "YES"
        }
        mock_invoke.return_value = "Confirmed! Appointment BK-DEF67890 with Dr Rao at West Clinic on 2026-12-04 at 17:30."

        event2 = {
            "httpMethod": "POST",
            "body": json.dumps(confirm_body),
            "headers": {"x-hub-signature-256": "sha256=test"}
        }

        response2 = lambda_handler(event2, {})
        assert response2["statusCode"] == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
