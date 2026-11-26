# WhatsApp Booking Agent on AWS AgentCore with Memory Support

This project implements a WhatsApp booking agent using AWS AgentCore with memory support. The system handles appointment scheduling through WhatsApp messages with rate limiting, privacy-focused phone number hashing, and AgentCore integration.

## Features

- **Privacy-first**: Phone numbers are SHA-256 hashed before use as keys
- **Rate limiting**: 5 requests per minute per phone number by default
- **AgentCore with memory**: Short-term and user preference memory types
- **Conditional writes**: Prevents double bookings (one per person, one per slot)
- **Idempotent seeding**: Initial slot data is idempotently seeded

## Project Structure

```
demos/multi-agent-demo1/
├── agent_workshop/      # Existing workshop code (untouched)
├── aws/
│   ├── lambda/
│   │   └── whatsapp_handler/
│   │       ├── store.py         # DynamoDB store with single-table design
│   │       ├── rate_guard.py    # Rate limiting logic
│   │       ├── agent.py         # AgentCore integration with memory
│   │       ├── whatsapp.py      # Meta webhook and messaging
│   │       └── handler.py       # Lambda entry point
│   │       └── __init__.py      # Module exports
│   │       └── requirements.txt # Python dependencies
│   ├── cdk/
│   │   ├── app.py               # CDK app entry
│   │   ├── stack.py             # AWS resources definition
│   │   └── requirements.txt     # CDK dependencies
│   └── tests/
│       ├── __init__.py
│       ├── test_store.py        # Store unit tests
│       ├── test_rate_guard.py   # Rate guard tests
│       ├── test_agent.py        # Agent tests
│       ├── test_whatsapp.py     # WhatsApp module tests
│       ├── test_handler.py      # Lambda handler tests
│       ├── test_e2e.py          # End-to-end tests
│       └── test_cdk.py          # CDK stack tests
├── docs/
│   └── WHATSAPP_SETUP.md        # Setup documentation
├── fixtures/
│   ├── clean_mr.json
│   └── risky_mr.json
├── tests/
│   └── test_workshop.py
├── README.md
└── pyproject.toml
```

## AWS Deployment

### Prerequisites

- AWS CLI configured with credentials
- Python 3.10+
- AWS CDK v2 (`pip install aws-cdk-cli`)
- Meta Developer account (free, no app review needed for test mode)
- Amazon Bedrock access enabled (Claude Haiku or Nova Lite)

### Deployment Steps

1. **Navigate to CDK directory**
   ```bash
   cd aws/cdk
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Bootstrap CDK (first time only)**
   ```bash
   cdk bootstrap
   ```

4. **Deploy the stack**
   ```bash
   cdk deploy --require-approval never
   ```

5. **Get the API Gateway URL (from output or logs)**
   The deploy output includes:
   - `BookingAgentStack.ApiEndpoint` - Your API Gateway URL
   - `BookingAgentStack.TableName` - DynamoDB table name
   - `BookingAgentStack.SecretArn` - Secrets Manager secret ARN

### Configure Meta Webhook

1. **Create Meta Developer App** (5 minutes, no app review needed for testing)
   1. Go to https://developers.facebook.com/apps
   2. Click "Create App" → "Connect with customers through WhatsApp"
   3. Fill in your business name and email
   4. Skip app review for test mode (we only need the test phone number)

2. **Get Test Credentials** (automatic with test mode)
   1. In your app dashboard, go to "WhatsApp" → "Quickstart"
   2. Click "Start using the API"
   3. Create or select a messaging account
   4. You'll get:
      - **Phone Number ID** - Your test number ID
      - **Temporary access token** - Valid for 24 hours (replace with system user token later)

3. **Register Test Phones** (up to 5 personal WhatsApp numbers)
   1. In WhatsApp Quickstart, click "Send and receive messages"
   2. Send a message from your personal WhatsApp to the test number
   3. The number will be registered for receiving messages

4. **Configure Webhook**
   1. In your app → "WhatsApp" → "Configuration"
   2. Callback URL: `https://<API-GW-URL>/`
   3. Verify Token: `whatsapp_booking_agent` (matching Secrets Manager)
   4. Subscribe to `messages` field

5. **Update Secrets Manager**
   Go to AWS Console → Secrets Manager → `BookingAgentStack-MetaCredentials` and update:
   - `access_token`: Your Meta access token (use system user token for production)
   - `app_secret`: Your Meta app secret
   - `verify_token`: `whatsapp_booking_agent`
   - `phone_number_id`: Your test phone number ID

### Test Your Deployment

1. Send a WhatsApp message from a registered phone: "What slots are available?"
2. You should receive a reply listing available slots
3. Send: "Book Dr Rao Friday 5 PM"
4. Follow the prompts to confirm the booking

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

## DynamoDB Table Structure

**Table Name**: `BookingTable` (created by CDK)

**Partition Key**: `PK` (String)  
**Sort Key**: `SK` (String)

### Item Types

#### Slot (Availability)
- `PK`: `SLOT#<slot_id>`
- `SK`: `SLOT`
- `available`: Boolean
- `clinic`: Clinic name
- `doctor`: Doctor name
- `time`: ISO datetime string (e.g., "2026-12-04 17:30")

#### Booking (Reservation)
- `PK`: `BOOKING#<phone_hash>`
- `SK`: `BOOKING`
- `name`: Patient name
- `slot_id`: ID of booked slot
- `reference`: Booking reference (BK-XXXX)
- `timestamp`: ISO timestamp

#### Rate (Rate Limiting)
- `PK`: `RATE#<phone_hash>`
- `SK`: `RATE`
- `count`: Integer (current count)
- `ttl`: Unix timestamp (60 seconds from last request)

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
# From project root
cd aws/tests
python -m pytest -v

# Run individual test files
python -m pytest test_store.py -v
python -m pytest test_rate_guard.py -v
python -m pytest test_agent.py -v
python -m pytest test_whatsapp.py -v
python -m pytest test_handler.py -v
```

### Test Coverage

- `test_store.py`: DynamoDB store operations (conditional writes, unique constraints)
- `test_rate_guard.py`: Rate limiting logic (exactly 5 requests per 60 seconds)
- `test_agent.py`: AgentCore integration (tools, fallback to Strands)
- `test_whatsapp.py`: Meta webhook signature verification, message parsing
- `test_handler.py`: Lambda handler (verification, message processing, rate limiting)
- `test_e2e.py`: End-to-end booking flow
- `test_cdk.py`: Stack resource creation

## Cost Optimization

- **DynamoDB**: PAY_PER_REQUEST billing (no capacity planning needed)
- **Lambda**: 512MB memory, 30-second timeout
- **Bedrock**: Claude Haiku or Amazon Nova Lite (cost-effective)
- **Rate limiting**: TTL-based cleanup of rate limit records
- **API Gateway**: HTTP API (cheaper than REST API)

## Security Considerations

- Phone numbers are hashed with SHA-256 before database operations
- Access tokens stored in Secrets Manager
- Lambda environment variables encrypted at rest
- IAM roles follow least privilege principle
- Conditional writes prevent race conditions
- Meta webhook signature verification validates incoming requests

## Troubleshooting

### Webhook not receiving messages

1. Check API Gateway logs in CloudWatch: `aws logs tail /aws/lambda/WhatsAppHandler`
2. Verify webhook URL in Meta console matches the API Gateway URL
3. Ensure TLS certificate is valid (API Gateway provides this automatically)

### Booking failures

1. Check DynamoDB table for existing booking with same phone hash
2. Verify slot is still marked as available
3. Review CloudWatch logs for error messages

### Rate limiting

- Default: 5 requests per 60 seconds per phone number
- Adjust `RATE_LIMIT_PER_MINUTE` environment variable in Lambda if needed

## Extensions

Potential enhancements:
- Support for image messages (medical documents)
- Appointment reminders via scheduled Lambda
- SMS fallback for non-WhatsApp users
- Admin dashboard for slot management
- Multi-language support

## License

This project is provided for educational and demonstration purposes.
