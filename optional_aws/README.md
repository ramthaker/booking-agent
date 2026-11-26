# Optional AWS/Strands integration path

This directory is **not required** for the local workshop. The local demos do not make model calls; they deliberately demonstrate multi-agent roles as deterministic functions, making them safe and reproducible on stage. The optional example invokes real Strands Agents SDK agents using Amazon Bedrock.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install 'strands-agents>=1.0'
export AWS_REGION=eu-west-1
export BEDROCK_MODEL_ID='<a-supported-enabled-bedrock-model-id>'
python optional_aws/strands_pattern.py
```

Your AWS principal needs **only model invocation privileges** for the selected Bedrock model. Model catalog availability, inference profile requirements, and exact IDs vary by region and account. Test before presenting; **nothing here deploys AgentCore**.

## How to turn this into AWS production architecture

1. SMS: register a supported two-way SMS origination identity with AWS End User Messaging SMS. Configure inbound SNS or Connect routing, opt-out handling, geographic and carrier requirements.
2. Protect event ingress: verify SNS authenticity, normalize channel identity, apply rate limits, and persist message IDs.
3. Orchestration: use Strands Agent-as-Tool pattern on AgentCore Runtime **or** the managed AgentCore Harness if it matches your required loop controls.
4. Tools: put scoped, typed APIs behind AgentCore Gateway where appropriate. Identity and per-tool authorization are application responsibilities too.
5. Booking: move SQLite to a transactional store, enforce conditional writes/unique slot constraints and idempotency, and never accept an LLM answer as proof of a booking.
6. MR: connect GitLab via scoped read-only token, redact and limit source context, run tests in isolated restricted CI; apply a deterministic blocking policy and keep merge approval human-owned.
7. Observability: trace event ID -> supervisor -> specialist -> tool -> state transition; report latency, correctness, false positives, escalations, token usage and unit cost.
8. Security: guard against prompt injection in SMS and untrusted code/MR descriptions; do not let retrieved content override tool permissions or policy.

For production use managed secrets, private networking where required, consent and retention policy, service-specific limits, versioned configuration, tests, alarms, and rollback.

## Optional true model-driven MR collaboration

From repository root, after configuring Bedrock:

```bash
python optional_aws/live_mr_multiagent.py
```

This invokes **four real model-driven specialist agents** through a Strands supervisor, using a *synthetic* MR fixture. It prints their advisory results and then independently runs a deterministic policy from the local repository. This does not evaluate model output quality automatically. Real integration requires validated structured findings, identity, tool permissions, read-only GitLab access, and independent testing.
