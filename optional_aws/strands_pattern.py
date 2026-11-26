"""OPTIONAL real Strands/Bedrock model exercise. Not used by the offline demo.

Run only after installing strands-agents, configuring a model ID and AWS credentials.
Read-only tool inputs only: no booking commits, no GitLab writes, no auto-merge.
The model may produce wrong answers; validate output independently.
"""
import os
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

MODEL_ID = os.environ.get('BEDROCK_MODEL_ID')
REGION = os.environ.get('AWS_REGION', 'eu-west-1')
if not MODEL_ID:
    raise SystemExit('Set BEDROCK_MODEL_ID to a Bedrock model available in your AWS account and region.')
model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

@tool
def read_only_available_slots(doctor: str) -> str:
    """Read-only appointment calendar lookup. Returns mock availability for Dr Rao only."""
    return 'Fictional Dr Rao: West Clinic, 2026-12-04 at 17:30 and 18:00. No slot is reserved.'

@tool
def read_only_review_policy() -> str:
    """Read-only engineering policy. High security findings require an independent human approval step."""
    return 'HIGH security finding => BLOCK. Do not post comments or merge automatically.'

availability = Agent(name='availability_specialist', description='Find appointment availability. Read-only.',
    model=model, tools=[read_only_available_slots], system_prompt='You only read available slots; never claim to book.', callback_handler=None)
policy = Agent(name='policy_specialist', description='Explain engineering review rules. Read-only.',
    model=model, tools=[read_only_review_policy], system_prompt='Explain policy; never approve or merge.', callback_handler=None)
supervisor = Agent(name='supervisor', model=model, tools=[availability, policy],
    system_prompt='Delegate to the best specialist. Never claim to have performed external side effects.')
print(supervisor('What appointment slots are available for Dr Rao?'))
print(supervisor('Can a high-severity security issue be merged without review?'))
