# Africa's Talking Integration Guide

## Overview

SatsRemit uses **Africa's Talking** for SMS notifications. Africa's Talking is a cost-effective SMS service provider with excellent coverage across Africa, including South Africa and Zimbabwe.

**Cost**: ~$0.002 per SMS (ZAR 0.01-0.03 depending on carrier)  
**Phase 1 Budget**: $5-10/month with typical transfer volumes

## Setup Instructions

### 1. Create Africa's Talking Account

1. Visit: https://africastalking.com
2. Sign up for a Free Trial account (includes $10 credits)
3. Verify your email

### 2. Get API Credentials

1. Log in to https://app.africastalking.com
2. Navigate to **Settings** → **API Keys**
3. Copy your:
   - **API Key** - Your authentication token
   - **Username** - Your account username (needed for API calls)

### 3. Configure Environment Variables

Update your `.env` file:

```bash
# .env
AFRICAS_TALKING_API_KEY=your_actual_api_key_here
AFRICAS_TALKING_USERNAME=your_username
AFRICAS_TALKING_SHORTCODE=optional_sender_id  # Leave empty to use username
```

### 4. (Optional) Setup Branded Sender ID

To send SMS with your own brand name or shortcode:

1. In Africa's Talking dashboard: **Settings** → **Sender IDs**
2. Request a new sender ID (e.g., "SATSREMIT")
3. Add to `.env`:
   ```bash
   AFRICAS_TALKING_SHORTCODE=SATSREMIT
   ```

**Note**: Sender ID approval takes 1-2 business days. Use defaults during testing.

## Message Types

### Receiver Notification (Pin Delivery)

```
SatsRemit Transfer
PIN: 1234
Amount: 100.00 ZAR
Ref: REF-XYZ123
Valid for 5 minutes
```

**Cost**: ~1 SMS per transfer

### Agent Alert

```
New Transfer Alert
Ref: REF-XYZ123
To: John Doe
Amount: 100.00 ZAR
Action: Verify receiver
```

**Cost**: ~1 SMS per transfer

### Sender Confirmation

```
Transfer Complete
Ref: REF-XYZ123
To: John Doe
Amount: 100.00 ZAR
Status: Funds delivered
```

**Cost**: ~1 SMS per completed transfer

### Total Cost Per Transfer
- **Receiver PIN**: 1 SMS
- **Agent Alert**: 1 SMS  
- **Sender Confirmation**: 1 SMS
- **Total**: 3 SMS × $0.002 = **~$0.006 per transfer**

At 1000 transfers/month: ~$6 total

## API Testing

### Test Sending SMS

```bash
# Using curl
curl -X POST https://api.sandbox.africastalking.com/version1/messaging/send \
  -H "ApiKey: YOUR_API_KEY_HERE" \
  -H "Accept: application/json" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=YOUR_USERNAME&to=%2B263712345678&message=Hello from SatsRemit"
```

### Expected Response (Success)

```json
{
  "SMSMessageData": {
    "Message": "Sent",
    "Recipients": [
      {
        "statusCode": 101,
        "number": "+263712345678",
        "status": "Success",
        "cost": "KES 0.80",
        "messageId": "ATXid_1234567890abcdef"
      }
    ]
  }
}
```

### Common Status Codes

| Code | Meaning |
|------|---------|
| 100 | Success |
| 101 | Success (but had duplicate recipients) |
| 102 | Success (some recipients invalid) |
| 400 | Bad request (check phone format) |
| 401 | Unauthorized (check API key) |
| 402 | Request failed (check message) |
| 403 | Forbidden (insufficient credits) |

## Phone Number Format

All phone numbers must include country code:

```
✓ Correct:
  +27701234567    (South Africa)
  +263712345678   (Zimbabwe)
  +265701234567   (Malawi)

✗ Incorrect:
  0701234567      (missing country code)
  27701234567     (missing + prefix)
  701234567       (no formatting)
```

## Cost Management

### Monitor Usage

In Africa's Talking dashboard:
1. **Credits** → View current balance
2. **Reports** → View SMS delivery status
3. **Logs** → See all API calls

### Free Trial

- Get $10 free credits on sign-up
- Perfect for Phase 1 testing
- Covers ~1,600 SMS messages

### Production Billing

Once in production:
1. Set up billing in dashboard
2. Link bank card for automatic top-ups
3. Set minimum balance alerts (e.g., $5)

## Troubleshooting

### SMS Not Sending

1. **Check phone format**: Must include country code (+27, +263, etc.)
2. **Check credits**: Ensure AF account has sufficient balance
3. **Check network**: Not all channels supported (SMS always available)
4. **Check logs**: Review delivery reports in AF dashboard

### High Latency

- SMS typically delivery in <30 seconds
- During peak hours may take longer
- Not ideal for real-time applications (but fine for remittance)

### Premium Routes

For critical messages, consider:
- SMS (default) - ~2-5 second latency
- USSD (Phase 2) - Immediate carrier confirmation
- Voice (Phase 2) - For call alerts

## Failover Strategy (Phase 2)

For production, implement fallback:

```python
# Pseudo-code
try:
    send_via_africas_talking(phone, message)
except TimeoutError:
    send_via_backup_provider(phone, message)  # e.g., Nexmo, Termii
```

Options for fallback:
- **Termii**: Nigeria-based, good Africa coverage
- **Vonage (Nexmo)**: Global coverage
- **Infobip**: Europe-based but African presence

## API Documentation

Full Africa's Talking documentation:
- https://africastalking.com/sms/api
- https://africastalking.com/contact-support

## Security Notes

### API Key Security

1. Never commit `.env` to git
2. Rotate API keys monthly
3. Use environment variables only
4. Add IP whitelist in Africa's Talking dashboard (Phase 2)

### Message Privacy

- SMS transmitted in plain text (standard SMS)
- Don't include sensitive info beyond PIN
- Never send full transfer details in SMS

### Rate Limiting

Africa's Talking has built-in rate limits:
- 100 requests per second (per account)
- 10,000 SMS per hour
- Compliant with local carrier regulations

## Cost Comparison

| Provider | Cost per SMS | Coverage | Best For |
|----------|-------------|----------|----------|
| Africa's Talking | $0.002-0.004 | Excellent (Africa-focused) | **SatsRemit** ✓ |
| Twilio | $0.01-0.03 | Global | International markets |
| Termii | $0.002-0.005 | Nigeria + Africa | Budget-conscious |
| Vonage (Nexmo) | $0.01-0.04 | Global | Enterprise |

**Winner for SA→ZW**: Africa's Talking (10-20x cheaper than Twilio!)

## Need Help?

1. Check [Africa's Talking documentation](https://africastalking.com/sms/api)
2. Review logs in AF dashboard
3. Contact Africa's Talking support
4. Check SatsRemit code in `src/services/notification.py`

---

**Next**: Implement and test notification service with real Africa's Talking account
