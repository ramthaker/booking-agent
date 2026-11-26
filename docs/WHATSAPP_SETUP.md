# WhatsApp Setup Guide

This guide walks you through setting up WhatsApp for the Booking Agent demo using Meta's test mode (no app review needed).

## Overview

The demo uses **Meta WhatsApp Cloud API** with a **test phone number**. This mode:

- ✅ No business verification required
- ✅ No app review needed
- ✅ Free for testing
- ⚠️ Can only message up to 5 pre-registered phone numbers
- ⚠️ Messages include "test" watermark

This is perfect for demos and development.

---

## Step 1: Create Meta Developer App

1. Go to https://developers.facebook.com/apps
2. Click **Create App**
3. Fill in:
   - **App name**: `Booking Agent Demo`
   - **Contact email**: Your email
4. Click **Next**
5. Select use case: **"Connect with customers through WhatsApp"**
6. Click **Next**
7. Select or create a Business Portfolio
8. Click **Create app**

---

## Step 2: Get Test Credentials

1. In your app dashboard, go to **WhatsApp** → **Quickstart**
2. Click **Start using the API**
3. Under **API Setup**, click **Create a WhatsApp Business account**
4. Fill in:
   - **WhatsApp Business Account Name**: `Booking Agent Demo`
   - **Display name**: `Booking Agent` (may be reviewed by Meta, use simple name)
   - **Timezone**: Your timezone
   - **Category**: `Healthcare` or `Shopping and Retail`
   - **Description**: `Demo booking assistant`
5. Click **Next**
6. Click **Next** on business profile
7. You'll get your credentials:
   - **Phone Number ID**: Something like `102934857612345`
   - **Temporary access token**: A long string (valid for 24 hours)

---

## Step 3: Register Test Phones

You can send messages to up to 5 personal WhatsApp numbers.

1. In the Quickstart page, click **Send and receive messages**
2. You'll see your test phone number (e.g., `+14155550000`)
3. **Send a message from each of your 5 test phones** to this number
4. The numbers will be automatically registered for receiving messages

---

## Step 4: Configure Webhook in AWS

1. Run `cdk deploy` and note the output:
   ```bash
   BookingAgentStack.ApiEndpoint = https://abc123.execute-api.ap-south-1.amazonaws.com/
   ```

2. In your Meta app → **WhatsApp** → **Configuration**:
   - **Callback URL**: `https://abc123.execute-api.ap-south-1.amazonaws.com/` (your API Gateway URL)
   - **Verify Token**: `whatsapp_booking_agent`
   - **Webhook fields**: Check `messages`

3. Click **Save Changes**

---

## Step 5: Update Secrets Manager

1. Go to AWS Console → **Secrets Manager**
2. Find the secret: `BookingAgentStack-MetaCredentials-XXXXX`
3. Click **Retrieve secret value**
4. Edit and update the JSON:

   ```json
   {
     "access_token": "<your_temporary_access_token>",
     "app_secret": "<your_app_secret_from_meta>",
     "verify_token": "whatsapp_booking_agent",
     "phone_number_id": "<your_phone_number_id>"
   }
   ```

5. Click **Save**

---

## Step 6: Test Your Setup

1. Send a message from a registered phone to your test number:
   ```
   What slots are available?
   ```

2. You should receive:
   ```
   Available slots:
   - Dr Rao at West Clinic on 2026-12-04 (17:30)
   - Dr Rao at West Clinic on 2026-12-04 (18:00)
   - Dr Shah at East Clinic on 2026-12-04 (16:00)
   ```

3. Try booking:
   ```
   Book Dr Rao Friday 5 PM
   ```

4. The agent will ask for your name, then confirm the booking.

---

## Troubleshooting

### No message received

- Check CloudWatch logs: `aws logs tail /aws/lambda/WhatsAppHandler --follow`
- Verify webhook URL matches API Gateway URL exactly
- Ensure `messages` field is subscribed in Meta configuration

### Signature verification failed

- Verify `META_APP_SECRET` in Secrets Manager matches your Meta app secret
- Check that `META_VERIFY_TOKEN` is `whatsapp_booking_agent`

### Booking fails

- Check DynamoDB table for existing booking with same phone hash
- Verify slot is still available in `SLOT#` items

### Rate limited

- Default is 5 requests per 60 seconds
- Wait a minute and try again
- Adjust `RATE_LIMIT_PER_MINUTE` environment variable if needed

---

## Going to Production

For production (beyond test mode):

1. **Complete app review** in Meta Developer Console
2. **Switch to permanent access tokens** using system users
3. **Configure business verification** for higher limits
4. **Register a production phone number** (may require TRAI in India)

For India specifically:
- Production numbers need **TRAI DLT registration**
- Use alphabetic Sender ID (e.g., `BOOKNG`)
- Register message templates in advance

---

## Cost

- **WhatsApp Cloud API**: Conversation-based pricing
- **Test mode**: Free (messages to registered test numbers)
- **Production**: ~$0.005 per message (varies by region)

See https://developers.facebook.com/docs/whatsapp/pricing for details.
