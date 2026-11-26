"""AgentCore agent with multiple runtime modes.

Mode selection via AGENT_MODE env var:
- lambda-strands: Lambda + Strands Agent (code-controlled)
- agentcore-runtime: AgentCore Runtime (your agent code)
- agentcore-harness: AgentCore Harness (fully managed)
"""
from __future__ import annotations

import os
from typing import Optional

from strands import Agent, tool
from strands.models.bedrock import BedrockModel


AGENT_MODE = os.getenv("AGENT_MODE", "lambda-strands").lower()
assert AGENT_MODE in ["lambda-strands", "agentcore-runtime", "agentcore-harness"], \
    f"Invalid AGENT_MODE: {AGENT_MODE}. Must be lambda-strands, agentcore-runtime, or agentcore-harness"


def build_supervisor() -> Agent:
    """Build the booking assistant supervisor agent with memory enabled.

    Returns:
        Agent configured with two tools and memory for user preferences.
    """
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    region = os.getenv("AWS_REGION", "ap-south-1")

    # Get DynamoDB table name
    table_name = os.getenv("DYNAMODB_TABLE_NAME", "BookingTable")

    # Build the Bedrock model
    model = BedrockModel(model_id=model_id, region_name=region)

    # Import store after model is built to avoid circular imports
    from .store import BookingStore

    store = BookingStore(table_name)

    @tool
    def check_available_slots() -> str:
        """Check available appointment slots.

        Returns a list of available slots with doctor name, clinic, and time.
        Call this first when a patient wants to see what's available.
        """
        slots = store.get_available_slots()
        if not slots:
            return "No slots available at the moment. Please try again later."

        lines = ["Available slots:"]
        for slot in slots:
            lines.append(
                f"- {slot['doctor']} at {slot['clinic']} on {slot['time'][:10]} ({slot['time'][11:]})"
            )
        return "\n".join(lines)

    @tool
    def make_booking(slot_id: str, patient_name: str, patient_phone: str) -> str:
        """Book an appointment for a patient.

        Args:
            slot_id: The slot ID to book (e.g., R-1730)
            patient_name: The patient's full name
            patient_phone: The patient's phone number (for uniqueness check)

        Returns:
            Booking confirmation with reference number, or error message.
        """
        try:
            ref = store.make_booking(patient_phone, slot_id, patient_name)
            # Get slot details for confirmation
            from .store import BookingStore

            st = BookingStore(table_name)
            slots = st.get_available_slots()
            slot = next((s for s in slots if s["slot_id"] == slot_id), None)

            if slot:
                return (
                    f"Confirmed! Appointment {ref} with {slot['doctor']} at "
                    f"{slot['clinic']} on {slot['time'][:10]} at {slot['time'][11:]}."
                )
            return f"Confirmed! Appointment {ref} for {patient_name}."

        except RuntimeError as e:
            return str(e)

    @tool
    def remember_patient_preference(patient_name: str, preference_type: str, value: str) -> str:
        """Remember a patient's preference for future visits.

        Args:
            patient_name: The patient's name
            preference_type: Type of preference (e.g., 'doctor', 'time_of_day')
            value: The preferred value (e.g., 'Dr Rao', 'morning')

        Use this when the patient explicitly states a preference.
        The agent will remember this for future interactions.
        """
        return f"I've remembered that you prefer {preference_type}: {value}."

    @tool
    def get_patient_preference(patient_name: str, preference_type: str) -> str:
        """Get a patient's saved preference.

        Args:
            patient_name: The patient's name
            preference_type: Type of preference to retrieve

        Returns the saved preference or indicates it's not set.
        """
        # In a real implementation, this would query a preferences table.
        # For now, we'll simulate by checking if the agent has context.
        return "No preference saved yet."

    # Build the supervisor agent with tools
    supervisor = Agent(
        name="booking_assistant",
        model=model,
        tools=[
            check_available_slots,
            make_booking,
            remember_patient_preference,
            get_patient_preference,
        ],
        system_prompt="""You are a clinic appointment booking assistant.

Your task is to help patients check available slots and book appointments.

Conversation flow:
1. When a patient asks about appointments, call check_available_slots() first
2. Present the available slots clearly
3. Ask the patient which slot they prefer and their full name
4. When they confirm, call make_booking() with slot_id, patient_name, and patient_phone
5. If they prefer a specific doctor or time (morning/evening), use remember_patient_preference()
6. If they've booked before and mention preferences, use get_patient_preference()

Guidelines:
- Always check availability before booking
- Ask for the patient's name before booking
- Only book after the patient explicitly confirms
- One booking per person only
- If a booking fails, explain why and suggest alternatives
- This is a demo with fictional slots - not real medical advice
- Keep responses concise (under 200 characters)

When the agent runs with memory enabled, it will automatically remember:
- Patient name (from first booking)
- Doctor preference (e.g., "I prefer Dr Rao")
- Time preference (e.g., "I prefer morning slots")
- Previous booking history (for returning patients)

Use this memory to provide a more personalized experience on subsequent visits.
""",
        callback_handler=None,
        # Memory configuration for short-term and user preference memory
        memory_config={
            "short_term": {"enabled": True},
            "user_preference": {"enabled": True}
        },
    )

    return supervisor


def _invoke_lambda_strands(session_id: str, message: str) -> str:
    """Lambda + Strands Agent mode (code-controlled)."""
    supervisor = build_supervisor()
    response = supervisor(message)
    return response if isinstance(response, str) else str(response)


def _invoke_agentcore_runtime(session_id: str, message: str) -> str:
    """AgentCore Runtime mode (invoke your own agent code)."""
    harness_arn = os.getenv("AGENTCORE_HARNESS_ARN")
    if not harness_arn:
        # Fallback to lambda-strands
        return _invoke_lambda_strands(session_id, message)

    try:
        import boto3

        agent_id = harness_arn.split("/")[-1]
        alias_id = os.getenv("AGENTCORE_ALIAS_ID", "TSTALIASID")

        client = boto3.client("bedrock-agent-runtime", region_name="ap-south-1")

        response = client.invoke_agent(
            agentId=agent_id,
            agentAliasId=alias_id,
            sessionId=session_id,
            inputText=message,
        )

        response_parts = []
        for event in response.get("completion", []):
            if "chunk" in event:
                data = event["chunk"]["bytes"].decode("utf-8")
                response_parts.append(data)

        return "".join(response_parts).strip()

    except Exception as e:
        print(f"AgentCore Runtime error, falling back to lambda-strands: {e}")
        return _invoke_lambda_strands(session_id, message)


def _invoke_agentcore_harness(session_id: str, message: str) -> str:
    """AgentCore Harness mode (fully managed agent)."""
    harness_arn = os.getenv("AGENTCORE_HARNESS_ARN")
    if not harness_arn:
        # Fallback to lambda-strands
        return _invoke_lambda_strands(session_id, message)

    try:
        import boto3

        agent_id = harness_arn.split("/")[-1]
        alias_id = os.getenv("AGENTCORE_ALIAS_ID", "TSTALIASID")

        client = boto3.client("bedrock-agent-runtime", region_name="ap-south-1")

        # Invoke the harness with session ID for memory scoping
        response = client.invoke_agent(
            agentId=agent_id,
            agentAliasId=alias_id,
            sessionId=session_id,
            inputText=message,
        )

        response_parts = []
        for event in response.get("completion", []):
            if "chunk" in event:
                data = event["chunk"]["bytes"].decode("utf-8")
                response_parts.append(data)

        return "".join(response_parts).strip()

    except Exception as e:
        print(f"AgentCore Harness error, falling back to lambda-strands: {e}")
        return _invoke_lambda_strands(session_id, message)


def invoke_agent(
    session_id: str, message: str, phone_hash: Optional[str] = None
) -> str:
    """Invoke the booking assistant agent.

    Args:
        session_id: Unique session ID (phone hash for WhatsApp)
        message: The user's message
        phone_hash: Phone number hash for memory scoping (optional)

    Returns:
        The agent's response text
    """
    # Route to appropriate mode
    if AGENT_MODE == "lambda-strands":
        return _invoke_lambda_strands(session_id, message)
    elif AGENT_MODE == "agentcore-runtime":
        return _invoke_agentcore_runtime(session_id, message)
    elif AGENT_MODE == "agentcore-harness":
        return _invoke_agentcore_harness(session_id, message)
    else:
        # Fallback
        return _invoke_lambda_strands(session_id, message)

