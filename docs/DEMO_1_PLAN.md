# Demo 1 Plan: WhatsApp Booking Agent

## Overview
A WhatsApp-based appointment booking system with AI-powered agents using Amazon Bedrock AgentCore. Users can book appointments by texting a WhatsApp number, and the system handles availability checking, booking, and user preferences with memory.

## Demo Flow

### Step 1: User Sends Message
- User texts: "What slots are available?"
- Or: "Book Dr Rao on Friday after 5 PM"

### Step 2: Agent Processes Request
AgentCore Harness runs the booking assistant with:
- **Short-term memory**: Remembers conversation context
- **User preference memory**: Remembers user's preferences (doctor, time preference)

Agent tools:
1. `check_available_slots()` - Queries DynamoDB for free slots
2. `make_booking(slot_id, patient_name, patient_phone)` - Books appointment
3. `remember_patient_preference()` - Remembers user preferences
4. `get_patient_preference()` - Retrieves saved preferences

### Step 3: Booking Confirmation
- Agent offers available slots
- User confirms with YES
- Agent books appointment in DynamoDB
- Returns confirmation reference (BK-XXXX)

## Architecture

```
WhatsApp User → Meta Cloud API → API Gateway → Lambda
                                               ↓
                                    +----------+----------+
                                    |  DynamoDB           |
                                    |  - SLOT# items      |
                                    |  - BOOKING# items   |
                                    |  - RATE# items      |
                                    +----------+----------+
                                               ↓
                                    +----------+----------+
                                    |  AgentCore Harness  |
                                    |  - Claude Haiku     |
                                    |  - Memory enabled   |
                                    |  - Tools wired      |
                                    +----------+----------+
                                               ↓
                                    +----------+----------+
                                    |  Meta WhatsApp API  |
                                    |  - Sends reply      |
                                    +----------+----------+
```

## Files to Deploy

### Lambda Code (`aws/lambda/whatsapp_handler/`)
| File | Purpose |
|---|---|
| `store.py` | DynamoDB operations (slots, bookings, rate limiting) |
| `rate_guard.py` | Rate limiting (5 req/min per phone) |
| `agent.py` | AgentCore integration with memory |
| `whatsapp.py` | Meta signature verify + message sending |
| `handler.py` | Lambda entry point |

### CDK Stack (`aws/cdk/`)
| File | Purpose |
|---|---|
| `app.py` | CDK entry point |
| `stack.py` | Creates DynamoDB, Lambda, API Gateway, Secrets Manager |
| `requirements.txt` | CDK dependencies |
| `cdk.json` | CDK configuration |

### CloudFormation (`aws/cloudformation/`)
| File | Purpose |
|---|---|
| `agentcore-harness.yaml` | Creates AgentCore Harness (optional) |

## Deployment Steps

1. **Install dependencies**
   ```bash
   cd aws/cdk
   pip install -r requirements.txt
   ```

2. **Deploy stack**
   ```bash
   cdk deploy --require-approval never
   ```

3. **Configure Meta**
   - Get API Gateway URL from CDK output
   - Set webhook URL, verify token, subscribe to messages
   - Update Secrets Manager with Meta credentials

4. **Test**
   - Send WhatsApp message from registered phone
   - Agent responds with available slots or booking confirmation

## Three Mode Demo (Optional)

The system supports three different agent modes:

| Mode | Command | Description |
|---|---|---|
| **lambda-strands** | Default | Lambda + Strands Agent (code-controlled) |
| **agentcore-runtime** | Set `AGENTCORE_HARNESS_ARN` | AgentCore Runtime (your agent code) |
| **agentcore-harness** | Set `AGENTCORE_HARNESS_ARN` | Fully managed AgentCore Harness |

### How to Switch Modes
```bash
aws lambda update-function-configuration \
  --function-name WhatsAppHandler \
  --environment "Variables={AGENT_MODE=agentcore-harness,AGENTCORE_HARNESS_ARN=<ARN>}"
```

## Cost Estimate (Monthly)

| Service | Cost (approx) |
|---|---|
| DynamoDB | $2.50 (PAY_PER_REQUEST, low traffic) |
| Lambda | $0.20 (1M requests, 256MB) |
| API Gateway | $3.50 (HTTP API, low traffic) |
| Secrets Manager | $0.40 (1 secret) |
| **Total** | **~$6.60/month** |

## Key Features

- **Privacy**: Phone numbers SHA-256 hashed
- **Rate limiting**: 5 requests/minute per phone
- **Idempotency**: Duplicate messages return same response
- **One booking per person**: Enforced in DynamoDB
- **One booking per slot**: Conditional writes prevent double-booking
- **User preferences**: Saved in AgentCore memory
- **Human escalation**: "urgent" keywords trigger human handoff

## Demo Script

1. **Introduction** (2 min)
   - Explain the demo architecture
   - Show the three-agent mode concept

2. **Show WhatsApp Interaction** (5 min)
   - User asks: "What slots are available?"
   - Agent responds with slots
   - User books: "YES"
   - Agent confirms booking

3. **Show Memory** (3 min)
   - User says: "I prefer Dr Rao in morning"
   - Agent remembers preference
   - Next time, agent uses saved preference

4. **Show Rate Limiting** (2 min)
   - Send rapid messages
   - Agent rejects with "too many requests"

5. **Show Code** (3 min)
   - Show Lambda handler
   - Show DynamoDB store
   - Show AgentCore integration

6. **Q&A** (5 min)

## Troubleshooting

| Issue | Solution |
|---|---|
| Webhook not receiving messages | Check API Gateway URL matches Meta config |
| Signature verification failed | Verify META_APP_SECRET in Secrets Manager |
| Booking fails | Check DynamoDB table for existing booking |
| Rate limited | Wait 60 seconds or adjust RATE_LIMIT_PER_MINUTE |
