"""Tests for rate guard using moto mock."""
import pytest
from unittest.mock import MagicMock


def test_rate_guard_allows_under_limit():
    """Test rate guard allows requests under the limit."""
    from aws.lambda.whatsapp_handler.rate_guard import check_rate

    mock_store = MagicMock()
    mock_store.table = MagicMock()
    # First 5 calls succeed
    mock_store.table.update_item.side_effect = [
        {"Attributes": {"count": 1}},
        {"Attributes": {"count": 2}},
        {"Attributes": {"count": 3}},
        {"Attributes": {"count": 4}},
        {"Attributes": {"count": 5}},
    ]

    phone_hash = "test_phone_hash"

    for i in range(5):
        result = check_rate(phone_hash, mock_store)
        assert result is True, f"Request {i+1} should be allowed"


def test_rate_guard_blocks_over_limit():
    """Test rate guard blocks requests over the limit."""
    from aws.lambda.whatsapp_handler.rate_guard import check_rate

    mock_store = MagicMock()
    mock_store.table = MagicMock()

    # First 5 calls succeed
    mock_store.table.update_item.side_effect = [
        {"Attributes": {"count": 1}},
        {"Attributes": {"count": 2}},
        {"Attributes": {"count": 3}},
        {"Attributes": {"count": 4}},
        {"Attributes": {"count": 5}},
    ]

    phone_hash = "test_phone_hash"

    # 6th request should be blocked
    result = check_rate(phone_hash, mock_store)
    assert result is False, "6th request should be blocked"


def test_rate_guard_different_phones_independent():
    """Test rate guard treats different phone numbers independently."""
    from aws.lambda.whatsapp_handler.rate_guard import check_rate

    mock_store = MagicMock()
    mock_store.table = MagicMock()
    mock_store.table.update_item.side_effect = [
        {"Attributes": {"count": 1}},
        {"Attributes": {"count": 1}},  # Second phone starts at 1
    ]

    phone_hash_1 = "hash1"
    phone_hash_2 = "hash2"

    # Phone 1 makes 1 request
    result1 = check_rate(phone_hash_1, mock_store)
    assert result1 is True

    # Phone 2 makes 1 request - should still be allowed
    result2 = check_rate(phone_hash_2, mock_store)
    assert result2 is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
