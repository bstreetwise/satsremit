# Fixing 400 Bad Request on Transfer Submission

## Problem
When trying to submit a transfer form, you get:
```
POST https://satsremit.com/api/transfers 400 (Bad Request)
```

## Root Causes

### 1. **No Agents Configured** (Most Common)
The error occurs because no agent has been set up for the receiver location you selected.

In [src/api/routes/public.py](src/api/routes/public.py#L183-188):
```python
agent = db.query(Agent).filter(
    Agent.location_code == request.receiver_location,
    Agent.status == AgentStatus.ACTIVE
).first()

if not agent:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"No active agent in {request.receiver_location}"
    )
```

### 2. **Poor Frontend Validation** (Now Fixed)
The form was not validating inputs properly before sending. Fixed by:
- ✅ Added phone format validation (E.164 format)
- ✅ Added location selection validation
- ✅ Ensured amount has exactly 2 decimal places
- ✅ Added better error messages to show API details

### 3. **Insufficient Error Details** (Now Fixed)
The API errors weren't being properly captured and displayed. Fixed by:
- ✅ Enhanced API error logging
- ✅ Detailed error extraction in frontend
- ✅ HTTP status codes displayed to user

## Solutions

### Quick Fix: Create Test Agents

Connect to the production database and insert agents:

```bash
# From your VPS:
ssh ubuntu@vm-1327.lnvps.cloud

# Connect to PostgreSQL:
psql -U satsremit_user -d satsremit_db

# Insert test agents for each location:
INSERT INTO agents (
    id, name, phone, location_code, location_name, 
    status, cash_balance_zar, commission_balance_sats
) VALUES
    (gen_random_uuid(), 'Agent Harare', '+263712345001', 'ZWE_HRR', 'Harare', 'ACTIVE', 50000.00, 0),
    (gen_random_uuid(), 'Agent Bulawayo', '+263712345002', 'ZWE_BUL', 'Bulawayo', 'ACTIVE', 50000.00, 0),
    (gen_random_uuid(), 'Agent Gweru', '+263712345003', 'ZWE_GWR', 'Gweru', 'ACTIVE', 50000.00, 0),
    (gen_random_uuid(), 'Agent Mutare', '+263712345004', 'ZWE_MUT', 'Mutare', 'ACTIVE', 50000.00, 0),
    (gen_random_uuid(), 'Agent Kwekwe', '+263712345005', 'ZWE_KWE', 'Kwekwe', 'ACTIVE', 50000.00, 0);

\q
```

### Or Use Python Script

Create `scripts/seed_agents.py`:
```python
import uuid
from decimal import Decimal
from sqlalchemy.orm import Session
from src.models.models import Agent, AgentStatus
from src.db.database import get_db_manager

def seed_agents():
    db_manager = get_db_manager()
    db = db_manager.get_session()
    
    locations = [
        ('ZWE_HRR', 'Harare'),
        ('ZWE_BUL', 'Bulawayo'),
        ('ZWE_GWR', 'Gweru'),
        ('ZWE_MUT', 'Mutare'),
        ('ZWE_KWE', 'Kwekwe'),
    ]
    
    for code, name in locations:
        agent = Agent(
            id=uuid.uuid4(),
            name=f'Agent {name}',
            phone=f'+263712{34500 + ord(code[-2]):05d}',
            location_code=code,
            location_name=name,
            status=AgentStatus.ACTIVE,
            cash_balance_zar=Decimal('50000.00'),
            commission_balance_sats=0
        )
        db.add(agent)
    
    db.commit()
    print("✅ Test agents created")
    db.close()

if __name__ == '__main__':
    seed_agents()
```

Run with:
```bash
cd /home/satsinaction/satsremit
python3 scripts/seed_agents.py
```

## How to Diagnose the Error

### 1. **Check Browser Console**
Press F12 or DevTools → Console to see:
- The exact payload being sent
- The API response details
- Error status and message

Example output:
```
api.js:22 API POST /api/transfers:
{
  status: 400,
  message: "No active agent in ZWE_HRR",
  response: {...}
}
```

### 2. **Check VPS Application Logs**
```bash
ssh ubuntu@vm-1327.lnvps.cloud
tail -f /tmp/app.log
```

### 3. **Test API Directly**
```bash
curl -X POST https://satsremit.com/api/transfers \
  -H "Content-Type: application/json" \
  -d '{
    "sender_phone": "+27712345678",
    "receiver_phone": "+263712345678",
    "receiver_name": "John Doe",
    "receiver_location": "ZWE_HRR",
    "amount_zar": 100.00
  }'
```

## Changes Made to Frontend

### app.js
- ✅ Added phone format validation
  - Accepts E.164 format: `+263123456789`
  - Accepts local format: `0123456789`
  - Rejects invalid formats

- ✅ Fixed decimal formatting
  - Amount always rounded to 2 decimal places
  - Ensures API `decimal_places=2` validation passes

- ✅ Enhanced error messages
  - Shows HTTP status code
  - Displays API response details
  - Helps diagnose issues

### api.js
- ✅ Improved error object
  - Captures full response data
  - Includes endpoint and method
  - Logs full request/response for debugging
  - Makes detailed error info available to callers

## Testing Checklist

After creating agents:

- [ ] Open http://satsremit.com/app or domain
- [ ] Go to "Send" tab
- [ ] Fill in form:
  - Your Phone: `+27712345678`
  - Recipient Name: `Test User`
  - Recipient Phone: `+263712345678`
  - Recipient Location: Select `Harare`
  - Amount: `100.00`
- [ ] Click "Continue to Payment"
- [ ] Verify you see payment QR code page
- [ ] check browser console (F12) for no errors

## Related Files

- [Transfer creation endpoint](src/api/routes/public.py#L137)
- [Agent validation](src/api/schemas.py#L18)
- [Frontend form handler](static/app/js/app.js#L168)
- [API module](static/app/js/api.js)

---

**Status:** ✅ Frontend validation improved. Awaiting agent database setup.
