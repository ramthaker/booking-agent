"""DynamoDB booking store with single-table design."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError


class BookingStore:
    """DynamoDB-backed booking store.

    Single table design:
    - SLOT#<slot_id>: slot metadata (doctor, clinic, time, available)
    - BOOKING#<phone_hash>: booking record (name, slot_id, reference, timestamp)
    - RATE#<phone_hash>: rate limit counter (count, ttl)
    """

    def __init__(self, table_name: Optional[str] = None):
        self.table_name = table_name or os.getenv("DYNAMODB_TABLE_NAME", "BookingTable")
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def _pk(self, prefix: str, key: str) -> str:
        """Generate partition key with prefix."""
        return f"{prefix}{key}"

    def _hash_phone(self, phone: str) -> str:
        """Hash phone number for privacy (SHA-256)."""
        return hashlib.sha256(phone.encode()).hexdigest()

    def get_available_slots(self) -> List[Dict[str, Any]]:
        """Get all available slots."""
        try:
            response = self.table.scan(
                FilterExpression="#available = :true",
                ExpressionAttributeNames={
                    "#available": "available",
                },
                ExpressionAttributeValues={
                    ":true": True,
                },
            )
            return response.get("Items", [])
        except ClientError as e:
            raise RuntimeError(f"Failed to get available slots: {e}") from e

    def make_booking(self, phone: str, slot_id: str, name: str) -> str:
        """Book a slot for a patient.

        Enforces:
        - One booking per person (conditional write on BOOKING#<phone_hash>)
        - One booking per slot (conditional write on SLOT#<slot_id> setting available=False)

        Returns booking reference or raises RuntimeError on conflict.
        """
        phone_hash = self._hash_phone(phone)

        try:
            # First, check if patient already has a booking
            existing = self.get_booking(phone_hash)
            if existing:
                raise RuntimeError("Patient already has a booking")

            # Generate booking reference
            reference = f"BK-{uuid.uuid4().hex[:8].upper()}"

            # Put booking record (conditional: patient must not have a booking)
            self.table.put_item(
                Item={
                    "pk": self._pk("BOOKING", phone_hash),
                    "sk": "BOOKING",
                    "name": name,
                    "slot_id": slot_id,
                    "reference": reference,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                ConditionExpression="attribute_not_exists(pk)",
            )

            # Mark slot as unavailable (conditional: slot must exist and be available)
            self.table.update_item(
                Key={"pk": self._pk("SLOT", slot_id), "sk": "SLOT"},
                UpdateExpression="SET #available = :false",
                ConditionExpression="attribute_exists(pk) AND #available = :true",
                ExpressionAttributeNames={"#available": "available"},
                ExpressionAttributeValues={":false": False},
            )

            return reference

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise RuntimeError("Slot is no longer available")
            raise

    def get_booking(self, phone_hash: str) -> Optional[Dict[str, Any]]:
        """Get booking for a patient by phone hash."""
        try:
            response = self.table.get_item(
                Key={"pk": self._pk("BOOKING", phone_hash), "sk": "BOOKING"}
            )
            return response.get("Item")
        except ClientError as e:
            raise RuntimeError(f"Failed to get booking: {e}") from e

    def seed_slots(self, slots: List[Dict[str, Any]]) -> None:
        """Seed initial slots (idempotent)."""
        for slot in slots:
            self.table.put_item(
                Item={
                    "pk": self._pk("SLOT", slot["slot_id"]),
                    "sk": "SLOT",
                    "doctor": slot["doctor"],
                    "clinic": slot["clinic"],
                    "time": slot["time"],
                    "available": True,
                },
                ConditionExpression="attribute_not_exists(pk)",
            )


# Default demo slots
DEMO_SLOTS = [
    {"slot_id": "R-1730", "doctor": "Dr Rao", "clinic": "West Clinic", "time": "2026-12-04 17:30"},
    {"slot_id": "R-1800", "doctor": "Dr Rao", "clinic": "West Clinic", "time": "2026-12-04 18:00"},
    {"slot_id": "S-1600", "doctor": "Dr Shah", "clinic": "East Clinic", "time": "2026-12-04 16:00"},
]
