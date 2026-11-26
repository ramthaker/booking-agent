"""Tests for WhatsApp signature verification and message handling."""
import pytest
import json
from unittest.mock import patch, MagicMock


def test_verify_signature_valid():
    """Test signature verification returns True for valid signature."""
    from aws.lambda.whatsapp_handler.whatsapp import verify_signature

    payload = b"test payload"
    app_secret = "test_secret"

    # Compute expected signature
    import hashlib
    import hmac

    expected_sig = "sha256=" + hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()

    result = verify_signature(payload, expected_sig, app_secret)
    assert result is True


def test_verify_signature_invalid():
    """Test signature verification returns False for invalid signature."""
    from aws.lambda.whatsapp_handler.whatsapp import verify_signature

    payload = b"test payload"
    app_secret = "test_secret"

    # Wrong signature
    result = verify_signature(payload, "sha256=invalid", app_secret)
    assert result is False


def test_verify_signature_empty():
    """Test signature verification returns False for empty input."""
    from aws.lambda.whatsapp_handler.whatsapp import verify_signature

    result = verify_signature(b"test", "", "secret")
    assert result is False


def test_parse_inbound_text_message():
    """Test parse_inbound extracts text message correctly."""
    from aws.lambda.whatsapp_handler.whatsapp import parse_inbound

    body = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "1234567890",
                                    "id": "wamid.123",
                                    "type": "text",
                                    "text": {"body": "Book Dr Rao on Friday"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    msg = parse_inbound(body)
    assert msg is not None
    assert msg["from"] == "1234567890"
    assert msg["text"] == "Book Dr Rao on Friday"


def test_parse_inbound_status_update():
    """Test parse_inbound returns None for status updates."""
    from aws.lambda.whatsapp_handler.whatsapp import parse_inbound

    body = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid.123",
                                    "status": "delivered"
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    msg = parse_inbound(body)
    assert msg is None


def test_parse_inbound_media_message():
    """Test parse_inbound returns None for media messages."""
    from aws.lambda.whatsapp_handler.whatsapp import parse_inbound

    body = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "1234567890",
                                    "type": "image",
                                    "image": {"mime_type": "image/jpeg"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    msg = parse_inbound(body)
    assert msg is None


def test_send_reply_success():
    """Test send_reply returns True on success."""
    from aws.lambda.whatsapp_handler.whatsapp import send_reply

    with patch("aws.lambda.whatsapp_handler.whatsapp.urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = send_reply(
            to_phone="1234567890",
            message_text="Hello!",
            phone_number_id="123456789012345",
            access_token="test_token"
        )

        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
