"""WhatsApp sender and Meta signature verification."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.request
import urllib.error


def verify_signature(payload: bytes, signature_header: str, app_secret: str) -> bool:
    """Verify Meta webhook signature.

    Args:
        payload: Raw request body bytes
        signature_header: X-Hub-Signature-256 header value (format: sha256=<hex>)
        app_secret: Meta app secret

    Returns:
        True if signature is valid, False otherwise
    """
    if not signature_header:
        return False

    # Extract hex from header (format: sha256=<hex>)
    if not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header.split("=", 1)[1]

    # Compute HMAC-SHA256
    expected = hmac.new(
        app_secret.encode(), payload, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, expected_signature)


def parse_inbound(body: dict) -> dict | None:
    """Parse inbound WhatsApp message.

    Args:
        body: Raw webhook request body

    Returns:
        Dict with 'from', 'message_id', 'text' if this is an inbound text message,
        None otherwise (e.g., status update, media message)
    """
    if not isinstance(body, dict):
        return None

    # Meta webhook structure
    entry = body.get("entry", [])
    if not isinstance(entry, list) or not entry:
        return None

    for e in entry:
        if not isinstance(e, dict):
            continue

        changes = e.get("changes", [])
        if not isinstance(changes, list):
            continue

        for change in changes:
            if not isinstance(change, dict):
                continue

            value = change.get("value", {})
            if not isinstance(value, dict):
                continue

            # Check for messages
            messages = value.get("messages", [])
            if not isinstance(messages, list) or not messages:
                # This might be a status update, not a message
                continue

            for msg in messages:
                if not isinstance(msg, dict):
                    continue

                # Only handle text messages
                if msg.get("type") != "text":
                    continue

                text_obj = msg.get("text", {})
                if not isinstance(text_obj, dict):
                    continue

                return {
                    "from": msg.get("from"),
                    "message_id": msg.get("id"),
                    "text": text_obj.get("body", ""),
                }

    return None


def send_reply(
    to_phone: str,
    message_text: str,
    phone_number_id: str | None = None,
    access_token: str | None = None,
) -> bool:
    """Send a WhatsApp reply.

    Args:
        to_phone: Recipient phone number
        message_text: Message content
        phone_number_id: WhatsApp Business Phone Number ID
        access_token: Meta access token

    Returns:
        True if message sent successfully, False otherwise
    """
    phone_number_id = phone_number_id or os.getenv("META_PHONE_NUMBER_ID")
    access_token = access_token or os.getenv("META_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        raise ValueError("META_PHONE_NUMBER_ID and META_ACCESS_TOKEN are required")

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message_text},
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200

    except urllib.error.HTTPError as e:
        # Log error but don't re-raise (Meta retries on non-200)
        error_body = e.read().decode() if e.fp else str(e)
        print(f"WhatsApp API error: {e.code} - {error_body}")
        return False

    except Exception as e:
        print(f"Failed to send WhatsApp reply: {e}")
        return False
