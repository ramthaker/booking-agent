"""Tests for DynamoDB store using moto mock."""
import pytest
import sys
from unittest.mock import patch, MagicMock

# Mock boto3 before importing store
mock_dynamodb = MagicMock()
mock_table = MagicMock()

# Patch boto3
sys.modules['boto3'] = MagicMock()
boto3_mock = sys.modules['boto3']
boto3_mock.resource = MagicMock(return_value=MagicMock())


def test_get_available_slots():
    """Test get_available_slots returns available slots."""
    from aws.lambda.whatsapp_handler.store import BookingStore

    # Mock the table
    store = BookingStore.__new__(BookingStore)
    store.table = MagicMock()
    store.table.scan.return_value = {
        "Items": [
            {"pk": "SLOT#R-1730", "doctor": "Dr Rao", "clinic": "West Clinic", "time": "2026-12-04 17:30", "available": True}
        ]
    }

    slots = store.get_available_slots()
    assert len(slots) == 1
    assert slots[0]["doctor"] == "Dr Rao"


def test_make_booking_success():
    """Test make_booking succeeds for first person on a free slot."""
    from aws.lambda.whatsapp_handler.store import BookingStore

    store = BookingStore.__new__(BookingStore)
    store.table = MagicMock()

    # First call to get_item returns None (no existing booking)
    store.table.get_item.return_value = {}
    # PutItem succeeds
    store.table.put_item.return_value = None
    # UpdateItem succeeds
    store.table.update_item.return_value = {"Attributes": {"pk": "SLOT#R-1730"}}

    ref = store.make_booking("+91-98765-43210", "R-1730", "Priya")

    # Verify conditional put was called with correct constraint
    store.table.put_item.assert_called_once()
    call_args = store.table.put_item.call_args
    assert "ConditionExpression" in call_args.kwargs
    assert "attribute_not_exists(pk)" in call_args.kwargs["ConditionExpression"]

    assert ref.startswith("BK-")


def test_make_booking_duplicate_patient():
    """Test make_booking raises error when patient already has booking."""
    from aws.lambda.whatsapp_handler.store import BookingStore

    store = BookingStore.__new__(BookingStore)
    store.table = MagicMock()

    # Simulate existing booking
    store.table.get_item.return_value = {
        "Item": {"pk": "BOOKING#abc123", "name": "Priya", "slot_id": "R-1730"}
    }

    with pytest.raises(RuntimeError, match="already has a booking"):
        store.make_booking("+91-98765-43210", "R-1730", "Priya")


def test_make_booking_slot_taken():
    """Test make_booking raises error when slot already taken."""
    from aws.lambda.whatsapp_handler.store import BookingStore

    store = BookingStore.__new__(BookingStore)
    store.table = MagicMock()

    store.table.get_item.return_value = {}
    store.table.put_item.side_effect = Exception("ConditionalCheckFailed")

    with pytest.raises(RuntimeError, match="no longer available"):
        store.make_booking("+91-98765-43210", "R-1730", "Priya")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
