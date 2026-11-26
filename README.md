# WhatsApp Booking Agent on AWS AgentCore with Memory

This project implements a WhatsApp booking agent using AWS AgentCore with memory support. The system handles appointment scheduling through WhatsApp messages with rate limiting, privacy-focused phone number hashing, and AgentCore integration.

## Features

- **Privacy-first**: Phone numbers are SHA-256 hashed before use as keys
- **Rate limiting**: 5 requests per minute per phone number by default
- **AgentCore with memory**: Short-term and user preference memory types
- **Conditional writes**: Prevents double bookings (one per person, one per slot)
- **Idempotent seeding**: Initial slot data is idempotently seeded

## Project Structure

```
aws/
├── lambda/whatsapp_handler/   # Lambda code for WhatsApp webhook
│   ├── store.py               # DynamoDB data layer
│   ├── rate_guard.py          # Rate limiting logic
│   ├── agent.py               # AgentCore integration with memory
│   ├── whatsapp.py            # Meta webhook and messaging
│   └── handler.py             # Lambda entry point
├── cdk/                        # AWS CDK infrastructure
│   ├── app.py                 # CDK entry point
│   ├── stack.py               # AWS resources definition
│   ├── requirements.txt       # CDK dependencies
│   └── cdk.json               # CDK configuration
├── tests/                      # Unit tests
│   ├── test_store.py
│   ├── test_rate_guard.py
│   ├── test_agent.py
│   ├── test_whatsapp.py
│   └── test_handler.py
├── cloudformation/             # AgentCore Harness CloudFormation
│   └── agentcore-harness.yaml
└── docs/
    └── WHATSAPP_SETUP.md      # Meta setup guide
```

## AWS Deployment

### Prerequisites

- AWS CLI configured with credentials
- Python 3.10+
- AWS CDK v2 (`npm install -g aws-cdk`)
- Meta Developer account with WhatsApp app configured
- Amazon Bedrock access enabled

### Deployment Steps

1. **Install CDK dependencies**
   ```bash
   cd aws/cdk
   pip install -r requirements.txt
   ```

2. **Bootstrap CDK (first time only)**
   ```bash
   cdk bootstrap
   ```

3. **Deploy the stack**
   ```bash
   cdk deploy --require-approval never
   ```

4. **Configure Meta Webhook**
   - Get API Gateway URL from CDK output
   - In Meta Developer Console → WhatsApp → Configuration
   - Callback URL: `https://<API-GW-URL>/`
   - Verify Token: `whatsapp_booking_agent`
   - Subscribe to `messages` field

5. **Update Secrets Manager**
   - Update `{StackName}-MetaCredentials` with:
     - `access_token`: Your Meta access token
     - `app_secret`: Your Meta app secret
     - `verify_token`: `whatsapp_booking_agent`
     - `phone_number_id`: Your Meta phone number ID

### Clean Up

```bash
cdk destroy
```

## Architecture

```
Meta WhatsApp Webhook
         |
         v
   API Gateway (HTTP API)
         |
         v
   Lambda Function (Python 3.12)
         |
         +---> DynamoDB Table (Single-table design)
         |       - SLOT# items (availability)
         |       - BOOKING# items (reservations)
         |       - RATE# items (rate limiting)
         |
         +---> Amazon Bedrock (AgentCore)
         |       - Short-term memory
         |       - User preference memory
         |
         +---> Meta WhatsApp API (responses)
```

## AgentCore Configuration

### Memory Types

- **Short-term memory**: Maintained within a session (30-minute window)
- **User preference memory**: Persists across sessions, scoped by phone hash

### Agent Tools

The agent has access to:

1. `check_available_slots()` - Returns available appointments
2. `make_booking(slot_id, patient_name, patient_phone)` - Books an appointment
3. `remember_patient_preference(patient_name, preference_type, value)` - Remembers user preferences
4. `get_patient_preference(patient_name, preference_type)` - Retrieves saved preferences

### Agent System Prompt

The agent is instructed to:
1. Ask for user name and preferences
2. Use `check_available_slots` tool to show availability
3. Use `make_booking` tool to schedule appointments
4. Confirm booking details with user
5. Remember preferences for future visits

## Testing

### Run Tests

```bash
cd aws/tests
python -m pytest -v
```

## Cost Optimization

- **DynamoDB**: PAY_PER_REQUEST billing
- **Lambda**: 512MB memory, 30-second timeout
- **Bedrock**: Claude Haiku or Amazon Nova Lite
- **API Gateway**: HTTP API (cheaper than REST API)

## Security

- Phone numbers hashed with SHA-256
- Access tokens in Secrets Manager
- IAM roles follow least privilege
- Meta webhook signature verification

## Next Steps

Run `docs/WHATSAPP_SETUP.md` for step-by-step Meta configuration guide.
