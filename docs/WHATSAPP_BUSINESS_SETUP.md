# WhatsApp Business API Setup Guide

This guide covers integrating WhatsApp Business API for SatsRemit notifications.

## Why WhatsApp Business API?

- **Cost**: Free for opted-in users (no per-message charges)
- **Reach**: Higher delivery rates in emerging markets (Zimbabwe, South Africa)
- **User Experience**: Native WhatsApp experience, no SMS fatigue
- **Compliance**: Built-in opt-in / opt-out mechanisms

## Prerequisites

1. Meta (Facebook) Business Account
2. Phone number for WhatsApp Business (can be existing or new)
3. Meta App for WhatsApp Business integration
4. Verified business information

## Step 1: Create Meta Business Account

1. Go to [business.facebook.com](https://business.facebook.com)
2. Click "Create Account"
3. Fill in business details:
   - Business Name: "SatsRemit"
   - Email: Your business email
   - Country: Zimbabwe or South Africa
4. Verify your email
5. Add business information and settings

## Step 2: Create WhatsApp Business Account

1. Navigate to [developers.facebook.com](https://developers.facebook.com)
2. Go to "Apps" → "Create App"
3. Select app type: "Business"
4. Fill in app details:
   - App Name: "SatsRemit WhatsApp"
   - App Purpose: "Messaging"
5. Complete the setup

## Step 3: Register Phone Number

1. In the app dashboard, find WhatsApp → "Getting Started"
2. Click "Get Started"
3. Select "Register Phone Number"
4. Choose your country (Zimbabwe or South Africa)
5. Enter phone number format:
   - Format: Full E.164 without + (e.g., `263712345678`)
   - Verify via SMS code sent to the number

## Step 4: Create Phone Number Display Name

1. After verification, set up your business profile:
   - Display Name: "SatsRemit"
   - Description: "Bitcoin remittance service"
   - Website: satsremit.com (if you have one)

## Step 5: Get API Credentials

1. In WhatsApp Business app settings, go to "API Setup"
2. Copy and save:
   - **Phone Number ID**: Found under "Phone Numbers"
   - **Business Account ID**: Found under "Settings" → "Business Information"
3. Create access token:
   - Go to "Settings" → "Tokens"
   - Generate new "Permanent" access token
   - **Save the token securely** (cannot be retrieved later)

## Step 6: Configure Environment Variables

Update `.env` file with your credentials:

```env
# WhatsApp Business API Credentials
WHATSAPP_BUSINESS_ACCOUNT_ID=YOUR_ACCOUNT_ID
WHATSAPP_BUSINESS_PHONE_NUMBER_ID=YOUR_PHONE_NUMBER_ID
WHATSAPP_BUSINESS_ACCESS_TOKEN=YOUR_ACCESS_TOKEN
```

## Step 7: Test Message Sending

### Via SatsRemit API

```bash
curl -X POST http://localhost:8000/test/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+263712345678",
    "message": "Test message from SatsRemit"
  }'
```

### Via Direct API Call

```bash
curl -X POST \
  "https://graph.instagram.com/v18.0/{PHONE_NUMBER_ID}/messages" \
  -H "Authorization: Bearer {ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "263712345678",
    "type": "text",
    "text": {
      "body": "Hello from SatsRemit!"
    }
  }'
```

### Sample Response (Success)

```json
{
  "messages": [
    {
      "id": "wamid.xxxxx",
      "message_status": "accepted"
    }
  ]
}
```

### Common Response Codes

- `200/201`: Message accepted by WhatsApp API
- `400`: Invalid request format (check phone number format, credentials)
- `401`: Authentication failed (check access token)
- `403`: Permission denied (token doesn't have message_send permission)
- `429`: Rate limited (wait before retrying)

## Step 8: Phone Number Formatting

WhatsApp requires E.164 format without the `+` prefix:

| Country | Example | Format |
|---------|---------|--------|
| Zimbabwe | +263 71 234 5678 | 263712345678 |
| South Africa | +27 82 123 4567 | 27821234567 |

The SatsRemit service automatically handles this conversion.

## Step 9: Enable Message Templates (Optional)

For high-volume messaging, set up message templates:

1. In WhatsApp Business dashboard → "Message Templates"
2. Create templates for:
   - PIN verification
   - Transfer confirmation
   - Payment completion
   - Agent alerts

### Benefits of Templates

- Lower cost per message
- Pre-approved content
- Better compliance tracking
- Higher throughput limits

### Example Template

```
Hi {{1}}, your SatsRemit verification PIN is {{2}}. 
This PIN is valid for 5 minutes. 
Reference: {{3}}
Amount: ZAR {{4}}
```

## Step 10: Webhook Configuration (Optional)

For delivery confirmations and read receipts:

1. In app settings → "Webhooks"
2. Set callback URL: `https://your-domain.com/webhooks/whatsapp`
3. Verify token: Generate and save
4. Subscribe to events:
   - `messages` (incoming)
   - `message_template_status_update` (template approvals)
   - `message_status_update` (delivery, read receipts)

## Troubleshooting

### Message Not Sending

1. **Check phone number format**: Must be E.164 without `+`
2. **Verify access token**: Ensure not expired (regenerate if needed)
3. **Check API version**: Using v18.0 or compatible
4. **Rate limiting**: Wait 1 minute between sending to same recipient
5. **Business verification**: Account must be in "GREEN" status

### Authentication Issues

- Verify `WHATSAPP_BUSINESS_ACCESS_TOKEN` is correct
- Check token hasn't expired (generate new if needed)
- Ensure token has `whatsapp_business_messaging` permission

### Phone Number Not Verified

- Number must be verified via SMS code
- Verification is one-time per account
- If verification fails, try with different number

### Recipients Not Receiving Messages

1. Verify phone numbers are correct (E.164 format)
2. Recipients must have WhatsApp account
3. Check recipient hasn't blocked business account
4. Ensure network connectivity on recipient side

## Support

For WhatsApp Business API support:
- Meta Business Help: [business.instagram.com/help](https://business.instagram.com/help)
- WhatsApp API Docs: [developers.facebook.com/docs/whatsapp](https://developers.facebook.com/docs/whatsapp)
- API Status: [status.meta.com](https://status.meta.com)

## Cost Analysis

**WhatsApp Business API**:
- Account: Free
- Phone number verification: Free
- Messaging: Free for opted-in users
- Template messaging: Tiered pricing (usually $0.0001 - $0.001 per message for high volume)

**Compared to Alternatives**:
- Twilio SMS: ~$0.05 per SMS (~$300-400/mo for SatsRemit volume)
- Africa's Talking SMS: ~$0.002 per SMS (~$12-20/mo)
- WhatsApp Business API: Free (~$0/mo base + optional templates)

## Integration with SatsRemit

The NotificationService in `src/services/notification.py` handles:

```python
# PIN delivery to receiver
await notification_service.send_pin_to_receiver(
    phone_number="+263712345678",
    pin="1234",
    transfer_reference="REF-XXXXX",
    amount_zar=500.00
)

# Agent alert for pending transfer
await notification_service.notify_agent_pending_transfer(
    agent_phone="+27821234567",
    transfer_reference="REF-XXXXX",
    receiver_name="John Doe",
    amount_zar=500.00
)

# Sender completion notification
await notification_service.notify_sender_completion(
    sender_phone="+263712345678",
    transfer_reference="REF-XXXXX",
    receiver_name="John Doe",
    amount_zar=500.00
)

# Admin alerts
await notification_service.send_admin_alert(
    admin_phone="+27821234567",
    alert_type="error",
    details="High transfer volume detected"
)
```

## Security Notes

- Never commit access tokens to version control
- Use environment variables (`.env`) for credentials
- Rotate access tokens quarterly
- Monitor token usage for suspicious activity
- Enable two-factor authentication on Meta Business Account
- Use IP whitelisting if available
- Log all notification sends for audit trail

## Next Steps

1. Test message sending to verify setup
2. Configure webhook for delivery tracking (optional)
3. Set up message templates for higher volume
4. Implement opt-in consent collection
5. Monitor message delivery rates and failures
