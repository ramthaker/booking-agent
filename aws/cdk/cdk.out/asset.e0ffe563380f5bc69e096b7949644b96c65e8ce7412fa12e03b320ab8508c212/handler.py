"""Lambda handler for WhatsApp webhook."""
from __future__ import annotations

import json
import os

from .store import BookingStore, DEMO_SLOTS
from .rate_guard import check_rate
from .agent import invoke_agent
from .whatsapp import verify_signature, parse_inbound, send_reply


def lambda_handler(event: dict, context: dict) -> dict:
    """Handle incoming webhook requests.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        HTTP response dict
    """
    # GET request - Meta webhook verification
    if event.get("httpMethod") == "GET":
        return handle_verification(event)

    # POST request - Inbound message
    if event.get("httpMethod") == "POST":
        return handle_inbound(event)

    return {"statusCode": 404, "body": "Not found"}


def handle_verification(event: dict) -> dict:
    """Handle Meta webhook verification challenge."""
    qs = event.get("queryStringParameters", {})

    mode = qs.get("hub.mode")
    verify_token = qs.get("hub.verify_token")
    challenge = qs.get("hub.challenge")

    if mode != "subscribe":
        return {"statusCode": 403, "body": "Invalid mode"}

    expected_token = os.getenv("META_VERIFY_TOKEN")
    if not expected_token:
        return {"statusCode": 500, "body": "Verify token not configured"}

    if verify_token != expected_token:
        return {"statusCode": 403, "body": "Invalid verify token"}

    if not challenge:
        return {"statusCode": 400, "body": "Missing challenge"}

    return {"statusCode": 200, "body": challenge}


def handle_inbound(event: dict) -> dict:
    """Handle inbound WhatsApp message."""
    # Read and verify signature
    body_bytes = event.get("body", "").encode() if isinstance(event.get("body"), str) else event.get("body", b"")
    if not body_bytes:
        return {"statusCode": 400, "body": "Empty body"}

    signature = event.get("headers", {}).get("x-hub-signature-256", "")
    app_secret = os.getenv("META_APP_SECRET", "demo_secret")

    if not verify_signature(body_bytes, signature, app_secret):
        return {"statusCode": 403, "body": "Invalid signature"}

    # Parse request body
    try:
        if isinstance(body_bytes, bytes):
            body = json.loads(body_bytes.decode())
        else:
            body = json.loads(body_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"statusCode": 400, "body": "Invalid JSON"}

    # Parse inbound message
    msg = parse_inbound(body)
    if msg is None:
        # Not a text message (e.g., status update)
        return {"statusCode": 200, "body": "OK"}

    from_phone = msg.get("from", "")
    message_text = msg.get("text", "").strip()

    if not from_phone or not message_text:
        return {"statusCode": 200, "body": "OK"}

    # Compute phone hash for privacy
    import hashlib

    phone_hash = hashlib.sha256(from_phone.encode()).hexdigest()

    # Rate guard
    store = BookingStore()
    if not check_rate(phone_hash, store):
        send_reply(
            from_phone,
            "Too many requests. Please wait a moment and try again.",
        )
        return {"statusCode": 200, "body": "Rate limited"}

    # Invoke agent
    try:
        reply = invoke_agent(
            session_id=phone_hash, message=message_text, phone_hash=phone_hash
        )
    except Exception as e:
        # Log error but always return 200 to Meta
        print(f"Agent error: {e}")
        reply = "I encountered an error processing your request. Please try again later."

    # Send reply
    success = send_reply(from_phone, reply)

    # Log for debugging (phone_hash, not phone)
    print(f"Message from {phone_hash[:16]}...: {message_text}")
    print(f"Reply: {reply}")
    print(f"Send success: {success}")

    return {"statusCode": 200, "body": "OK"}
