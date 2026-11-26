"""Tests for AgentCore agent with tools."""
import pytest
from unittest.mock import patch, MagicMock


def test_agent_builds_with_tools():
    """Test agent is built with required tools."""
    from aws.lambda.whatsapp_handler.agent import build_supervisor

    # Mock BedrockModel and boto3
    with patch("aws.lambda.whatsapp_handler.agent.BedrockModel") as mock_model, \
         patch("boto3.resource"):
        mock_model.return_value = MagicMock()
        supervisor = build_supervisor()

        # Agent should be created
        assert supervisor is not None
        # Verify tools are available
        assert hasattr(supervisor, "tools")
        assert len(supervisor.tools) >= 2  # check_available_slots, make_booking at minimum


def test_invoke_agent_returns_response():
    """Test invoke_agent returns a response string."""
    from aws.lambda.whatsapp_handler.agent import invoke_agent

    # Mock the supervisor
    mock_supervisor = MagicMock()
    mock_supervisor.return_value = "I found slots for you."

    with patch("aws.lambda.whatsapp_handler.agent.build_supervisor", return_value=mock_supervisor):
        response = invoke_agent(session_id="test123", message="What slots are available?")

        assert isinstance(response, str)
        assert "slots" in response.lower()


def test_invoke_agent_fallback_to_strands():
    """Test invoke_agent falls back to Strands when AgentCore not configured."""
    from aws.lambda.whatsapp_handler.agent import invoke_agent

    # Mock BedrockModel and boto3
    with patch("aws.lambda.whatsapp_handler.agent.BedrockModel") as mock_model, \
         patch("boto3.resource"), \
         patch("boto3.client") as mock_client:

        mock_model.return_value = MagicMock()
        mock_supervisor = MagicMock()
        mock_supervisor.return_value = "Fallback response"
        mock_client.return_value.invoke_agent.side_effect = Exception("Not available")

        with patch("aws.lambda.whatsapp_handler.agent.build_supervisor", return_value=mock_supervisor):
            response = invoke_agent(session_id="test123", message="Test")

            # Should return fallback response
            assert isinstance(response, str)
            assert "Fallback" in response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
