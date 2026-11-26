# Implementation Plan: aws-interactive-deployment

## Overview

Implement the AWS deployment of the Demo 1 appointment-booking concierge. The primary channel is two-way SMS via AWS End User Messaging; the web UI is a secondary demo-audience channel sharing the same agent and DynamoDB path. Infrastructure is defined in CDK Python. Work is grouped into eight ordered groups: CDK infrastructure, DynamoDB schema and seeding, Strands agent layer, SMS Lambda handler, Web API Lambda handler, Web UI update, tests, and README/docs.

## Tasks

- [ ] 1. Set up CDK project structure and core interfaces
  - Create `aws/cdk/` with `app.py`, `booking_stack.py`, `requirements.txt`
  - Create `aws/lambda/` with `config.py`, `booking_ddb.py`, `agents.py`, `handler_web.py`, `handler_sms.py`, `requirements.txt`
  - Create `scripts/deploy.sh` and `cdk.json`
  - Define the `BookingReply` dataclass and `BookingStore` abstract interface in `aws/lambda/booking_ddb.py`
  - _Requirements: 1.1, 7.1, 7.3_

- [ ] 2. CDK infrastructure stack
  - [ ] 2.1 Define DynamoDB table, S3 bucket, and CloudFront distribution in `booking_stack.py`
    - Single-table with `pk` (HASH) + `sk` (RANGE), PAY_PER_REQUEST
    - S3 bucket with `BlockPublicAcls=True`, `BlockPublicPolicy=True`; CloudFront OAC origin
    - Enable PITR when `DEPLOY_STAGE=prod`
    - _Requirements: 1.1, 1.5, 1.6, 2.1_

  - [ ] 2.2 Define Web API Lambda and API Gateway in `booking_stack.py`
    - Python 3.12, 512 MB, 30 s timeout; env vars `BEDROCK_MODEL_ID`, `AWS_REGION`, `DYNAMODB_TABLE_NAME`, `AGENTCORE_RUNTIME_ARN`
    - REST API with `POST /chat`, `POST /booking/race`, `GET /metrics`; request body limit 8192 B; CORS enabled
    - Fail CDK synth with descriptive error if `BEDROCK_MODEL_ID` absent at synth time
    - _Requirements: 1.2, 1.3, 1.4, 4.1, 4.2, 4.3, 4.5, 7.5_

  - [ ] 2.3 Define SMS Lambda, SNS topic, and End User Messaging wiring in `booking_stack.py`
    - SNS topic `InboundSMSTopic`; SMS Lambda subscribed to the topic
    - SMS Lambda environment: same vars as Web API Lambda plus `ORIGINATION_NUMBER` (from Secrets Manager)
    - IAM policy: `sns:Publish` for outbound SMS, `sms-voice:SendTextMessage` for End User Messaging SDK
    - _Requirements: 1.1, 1.4_

  - [ ] 2.4 Define Seed CustomResource Lambda in `booking_stack.py`
    - Small seed Lambda with `PutItem` + `attribute_not_exists(pk)` for the three synthetic slots
    - `CustomResource` triggers seed Lambda on deploy; idempotent across re-deployments
    - _Requirements: 2.2_

  - [ ]* 2.5 Write CDK snapshot tests for the synthesised CloudFormation template
    - Assert DynamoDB KeySchema, Lambda env vars, S3 block-public-access, API Gateway routes, IAM actions (no wildcards)
    - _Requirements: 1.1, 1.2, 1.4, 1.5_

- [ ] 3. DynamoDB schema and booking store
  - [ ] 3.1 Implement `DynamoBookingStore` in `aws/lambda/booking_ddb.py`
    - `list_available_slots(doctor)`: Query `SLOT#` items, return only un-booked slots
    - `check_idempotency(message_id)` / `store_idempotency(message_id, reply)`: read/write `MSG#` with 24 h TTL
    - `confirm_booking(customer, slot_id)`: `PutItem` with `attribute_not_exists(pk)` on `BOOKING#{slot_id}`; catch `ConditionalCheckFailedException` → return `CONFLICT`
    - `get_conversation(customer)` / `put_conversation(customer, state, offered_slot)`: read/write `CONV#` items
    - `summary()`: count `BOOKING#` and `SLOT#` items, return dict for `/metrics`
    - _Requirements: 2.1, 2.3, 2.4, 2.5_

  - [ ] 3.2 Implement hashed phone-number key helper
    - `hash_phone(phone: str) -> str`: SHA-256 of normalized E.164 number; used as `customer` value for SMS channel bookings
    - Stored as `pk` prefix only — raw phone number never written to DynamoDB
    - _Requirements: 8.1_

  - [ ] 3.3 Implement `run_slot_race` in `aws/lambda/booking_ddb.py`
    - Pre-populate 20 `CONV#race-customer-{n}` items offering slot `R-1730`
    - `ThreadPoolExecutor(max_workers=20)` with `Barrier` for synchronised start
    - Return `{"contenders": 20, "confirmed": 1, "conflicts": 19, "booking_rows": 1}`; log ERROR if invariant violated
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 3.4 Write property test for slot booking mutual exclusion (Property 1)
    - **Property 1: Slot Booking Mutual Exclusion**
    - **Validates: Requirements 2.3, 2.4, 6.3**
    - Generate random slot IDs and N (2–50 concurrent callers); mock DynamoDB conditional write in-process; assert exactly 1 CONFIRMED and N−1 CONFLICT

  - [ ]* 3.5 Write property test for idempotency (Property 2)
    - **Property 2: Idempotency of Message Processing**
    - **Validates: Requirements 2.5**
    - Generate random `message_id` strings and `BookingReply` instances; store then replay; assert second reply equals first and agent not invoked again

  - [ ]* 3.6 Write property test for booking conditional write atomicity (Property 7)
    - **Property 7: Booking Conditional Write Atomicity**
    - **Validates: Requirements 2.3, 6.3**
    - After one CONFIRMED booking in DynamoDB for a slot, assert all subsequent `confirm_booking` calls return CONFLICT and table contains exactly one `BOOKING#` item for that slot

- [ ] 4. Strands agent layer
  - [ ] 4.1 Implement `query_available_slots` tool and `build_supervisor()` in `aws/lambda/agents.py`
    - `@tool query_available_slots(doctor)`: calls `DynamoBookingStore.list_available_slots`, read-only
    - `availability_specialist` Agent: `BedrockModel`, `tools=[query_available_slots]`, read-only system prompt
    - `supervisor` Agent: `BedrockModel`, `tools=[availability_specialist]`, system prompt forbids claiming to commit bookings
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ] 4.2 Implement `invoke_supervisor()` with AgentCore Runtime / direct-Strands fallback in `aws/lambda/agents.py`
    - If `AGENTCORE_RUNTIME_ARN` set: call `bedrock-agentcore-runtime` `invoke_agent`, stream and join response chunks
    - Else: call `str(supervisor(message))` directly
    - _Requirements: 3.6_

  - [ ]* 4.3 Write property test for agent reasoning propagation (Property 6)
    - **Property 6: Agent Reasoning Propagation**
    - **Validates: Requirements 3.5**
    - Generate random non-empty strings as mock agent output; assert `BookingReply.message` equals that string with no truncation or wrapping

- [ ] 5. SMS Lambda handler
  - [ ] 5.1 Implement emergency-escalation detection in `aws/lambda/handler_sms.py`
    - `is_emergency(text)`: case-insensitive substring check for `"urgent"` and `"chest pain"`
    - Returns `BookingReply(state="ESCALATED", message="For a medical emergency, contact local emergency services immediately.")`; Supervisor Agent never invoked
    - _Requirements: 8.3_

  - [ ] 5.2 Implement multi-turn conversation flow in `aws/lambda/handler_sms.py`
    - Extract sender phone number from SNS event; normalise to E.164; hash via `hash_phone()`
    - Load `CONV#` state; if no active conversation, invoke supervisor to offer slots
    - If `CONV#` state is `OFFERED` and inbound text matches `YES` (case-insensitive), call `confirm_booking`; reply with reference or conflict notice
    - Write outbound SMS reply via `boto3` End User Messaging SDK (`sms-voice:SendTextMessage`, origination number from env)
    - Idempotency guard: check `MSG#{message_id}` before any agent invocation
    - _Requirements: 2.3, 2.4, 2.5, 3.1, 3.5_

  - [ ]* 5.3 Write property test for emergency escalation bypass (Property 5)
    - **Property 5: Emergency Escalation Bypasses the Agent**
    - **Validates: Requirements 8.3**
    - Generate messages containing `"urgent"` or `"chest pain"` in any position/case/context; assert reply contains emergency text and no agent invocation occurred

- [ ] 6. Web API Lambda handler
  - [ ] 6.1 Implement `config.py` fail-fast env-var validation
    - `validate_env()` checks `BEDROCK_MODEL_ID` and `DYNAMODB_TABLE_NAME`; `sys.exit(1)` with `logging.critical` on missing vars; called at module level in both Lambda handlers
    - _Requirements: 7.1, 7.3_

  - [ ] 6.2 Implement `handler_web.py` routing: `/chat`, `/booking/race`, `/metrics`
    - Module-level `DynamoBookingStore` and `build_supervisor()` for warm-invocation reuse
    - `_handle_chat`: parse + validate `customer` (≤100), `text` (≤2000), `message_id` (≤128); call `store.on_message`; return `BookingReply.to_dict()`
    - `_handle_race`: call `run_slot_race(store)`; return 500 if `confirmed != 1`
    - CORS headers on all responses; unhandled exceptions return 500 with `{"error": "Demo operation failed"}` (no stack trace)
    - _Requirements: 4.1, 4.2, 4.4, 4.5, 4.6, 6.1–6.4_

  - [ ]* 6.3 Write property test for input validation (Property 3)
    - **Property 3: Input Validation Rejects Oversized Fields**
    - **Validates: Requirements 4.4**
    - Generate combinations where at least one field exceeds its max length; assert HTTP 400 with non-empty `error` field and no DynamoDB writes

  - [ ]* 6.4 Write property test for race isolation (Property 4)
    - **Property 4: Race Isolation — Non-Race Customers Unaffected**
    - **Validates: Requirements 6.5**
    - Pre-populate arbitrary non-race conversation records; run `run_slot_race`; assert those records are identical afterwards

- [ ] 7. Checkpoint — core Lambda + DynamoDB complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Web UI update
  - [ ] 8.1 Update `web/index.html` API base URL and response rendering
    - Replace hardcoded `/api/*` paths with `window.API_BASE` constant (injected by CDK BucketDeployment string substitution)
    - Render `CONFIRMED` with booking reference, `CONFLICT` without reference number, all other states with `agent` + `state` + `message`
    - Retain disclaimer: `"Educational fixture · No phone number provisioned · No live clinic · AWS demo deployment."`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

  - [ ] 8.2 Wire `/metrics` refresh into the web UI
    - After each `POST /chat` response, fetch `GET /metrics` and update slot-availability display
    - _Requirements: 5.5_

- [ ] 9. Tests — integration smoke and unit coverage
  - [ ] 9.1 Write unit tests for `DynamoBookingStore` with mocked DynamoDB
    - Test each entity CRUD path: slots, bookings, conversations, idempotency records, escalations
    - Test `ConditionalCheckFailedException` → CONFLICT path
    - _Requirements: 2.3, 2.4, 2.5_

  - [ ] 9.2 Write unit tests for `handler_web.py` routing
    - Test all three routes with valid input; test 400 on oversized fields; test 500 on unhandled exception; test OPTIONS CORS preflight
    - _Requirements: 4.1–4.6_

  - [ ] 9.3 Write unit tests for SMS Lambda flow in `handler_sms.py`
    - Test slot-offer flow, YES-confirmation flow, CONFLICT reply, idempotent replay, emergency-escalation bypass
    - Verify outbound SMS send call arguments (origination number, destination, message body)
    - _Requirements: 2.3, 2.5, 8.3_

  - [ ] 9.4 Write unit tests for `hash_phone` and `is_emergency` helpers
    - `hash_phone`: same input always produces same output; different inputs produce different hashes; raw number not present in output
    - `is_emergency`: true for `"urgent"`, `"URGENT"`, `"chest pain"`, mixed-case; false for unrelated text
    - _Requirements: 8.1, 8.3_

- [ ] 10. Final checkpoint — all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. README and docs update
  - [ ] 11.1 Add `## AWS Deployment` section to `README.md`
    - Prerequisites: Python 3.10+, AWS CDK v2, AWS account with Bedrock model access, End User Messaging origination number registration, `strands-agents` package
    - Deploy commands: set env vars, `cdk bootstrap`, `cdk deploy BookingStack`, URL output location
    - Test instructions: send test SMS to provisioned number, open CloudFront URL for web UI, `POST /booking/race` to verify race invariant
    - IAM permissions a deployer needs: `cloudformation:*`, `iam:CreateRole`, `iam:AttachRolePolicy`, `lambda:*`, `dynamodb:*`, `s3:*`, `apigateway:*`, `bedrock:InvokeModel`, `sms-voice:*`
    - Safety statement: synthetic data only, no real patients/clinicians/SMS traffic in production
    - Retain all existing local-demo instructions unchanged
    - _Requirements: 9.1–9.5, 8.6_

  - [ ] 11.2 Add inline demo-safety disclaimer to CDK stack module docstring
    - State this is a workshop demo, not medical advice, not a production system
    - _Requirements: 8.6_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP.
- Each task references specific requirements for traceability.
- Property tests use Hypothesis; unit tests use pytest with `moto` or `unittest.mock` for DynamoDB.
- The SMS channel and Web API channel share `DynamoBookingStore`, `agents.py`, and `config.py` — only the Lambda entry-point differs.
- Phone numbers are SHA-256 hashed before use as DynamoDB partition keys; raw numbers are never stored.
- The CDK stack does **not** auto-provision the End User Messaging origination number — number registration requires manual 10DLC/toll-free carrier approval. The deploy script documents this prerequisite.
- `run_slot_race` uses `threading.Barrier` to maximise concurrency inside a single Lambda invocation; this is sufficient to demonstrate the DynamoDB conditional-write invariant without real distributed load.
- Checkpoints at tasks 7 and 10 gate further work on verified correctness.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3", "2.4"] },
    { "id": 2, "tasks": ["3.1", "3.2"] },
    { "id": 3, "tasks": ["3.3", "4.1"] },
    { "id": 4, "tasks": ["4.2"] },
    { "id": 5, "tasks": ["3.4", "3.5", "3.6", "4.3", "5.1"] },
    { "id": 6, "tasks": ["5.2", "6.1"] },
    { "id": 7, "tasks": ["2.5", "5.3", "6.2"] },
    { "id": 8, "tasks": ["6.3", "6.4"] },
    { "id": 9, "tasks": ["7"] },
    { "id": 10, "tasks": ["8.1", "8.2"] },
    { "id": 11, "tasks": ["9.1", "9.2", "9.3", "9.4"] },
    { "id": 12, "tasks": ["10"] },
    { "id": 13, "tasks": ["11.1", "11.2"] }
  ]
}
```
