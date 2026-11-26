"""Rate guard using DynamoDB atomic counters."""
from __future__ import annotations

import os
import time
from typing import Optional

from .store import BookingStore


def check_rate(phone_hash: str, store: Optional[BookingStore] = None) -> bool:
    """Check if the phone number is within rate limits.

    Args:
        phone_hash: SHA-256 hash of the phone number
        store: BookingStore instance (optional, reads from env var)

    Returns:
        True if request is allowed, False if rate limited
    """
    store = store or BookingStore()
    limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))
    window_seconds = 60

    pk = f"RATE#{phone_hash}"

    try:
        current_time = int(time.time())
        ttl = current_time + window_seconds

        # Atomic counter update: increment and check if under limit
        response = store.table.update_item(
            Key={"pk": pk, "sk": "RATE"},
            UpdateExpression="SET #count = if_not_exists(#count, :zero) + :one, "
            "#ttl = if_not_exists(#ttl, :ttl)",
            ConditionExpression="#count < :limit",
            ExpressionAttributeNames={"#count": "count", "#ttl": "ttl"},
            ExpressionAttributeValues={
                ":one": 1,
                ":zero": 0,
                ":limit": limit,
                ":ttl": ttl,
            },
            ReturnValues="ALL_NEW",
        )

        return True

    except Exception:
        # ConditionalCheckFailedException or any other error means rate limited
        return False


def increment_rate(phone_hash: str, store: Optional[BookingStore] = None) -> None:
    """Increment the rate counter for a phone number.

    This should only be called if check_rate returned True.
    Use check_rate() which handles both check and increment atomically.
    """
    store = store or BookingStore()
    current_time = int(time.time())
    ttl = current_time + 60

    store.table.update_item(
        Key={"pk": f"RATE#{phone_hash}", "sk": "RATE"},
        UpdateExpression="SET #count = if_not_exists(#count, :zero) + :one, "
        "#ttl = if_not_exists(#ttl, :ttl)",
        ExpressionAttributeNames={"#count": "count", "#ttl": "ttl"},
        ExpressionAttributeValues={
            ":one": 1,
            ":zero": 0,
            ":ttl": ttl,
        },
    )
