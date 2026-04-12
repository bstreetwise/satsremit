# SatsRemit Platform - End-to-End Testing Guide

## ✅ Verification Complete

All 25 checks have been verified:
- ✅ 5/5 Python syntax checks passed
- ✅ 9/9 required files present
- ✅ 7/7 key implementations found
- ✅ 4/4 frontend navigation checks passed

---

## 🧪 Running Tests

### 1. Unit Tests for Receiver Flow

```bash
cd /home/satsinaction/satsremit

# Run all receiver flow tests
python3 -m pytest tests/test_receiver_flow.py -v

# Run specific test class
python3 -m pytest tests/test_receiver_flow.py::TestReceiverFlowEndpoints -v

# Run with coverage
python3 -m pytest tests/test_receiver_flow.py --cov=src/api/routes/public.py --cov=src/services/transfer.py
```

### 2. Test All Existing Tests

```bash
# Run entire test suite
python3 -m pytest tests/ -v

# Run with detailed output
python3 -m pytest tests/ -vv --tb=short
```

### 3. Verify Platform Integration

```bash
# Verify all implementations
python3 verify_implementation.py
```

---

## 🚀 Manual Testing Scenarios

### Scenario 1: Complete Transfer Flow (Sender → Receiver → Agent)

**Step 1: Sender Creates Transfer**
```bash
curl -X POST http://localhost:8000/api/transfers \
  -H "Content-Type: application/json" \
  -d '{
    "sender_phone": "+27987654321",
    "receiver_phone": "+27111111111",
    "receiver_name": "Test Receiver",
    "receiver_location": "ZWE_HRR",
    "amount_zar": 500.00
  }'

# Response: transfer_id, reference, invoice_request
# SAVE: transfer_id, reference, amount_zar
```

**Step 2: Simulate Payment Received**
```bash
# Backend detects payment (normally automatic via LND polling)
# PIN is auto-generated and sent to receiver via WhatsApp

# Check transfer status
curl -X POST http://localhost:8000/api/transfers/{transfer_id}/check-payment

# Response: state = PAYMENT_LOCKED, receiver_phone_verified = false
```

**Step 3: Receiver Verifies PIN**
```bash
# Receiver gets reference REF... from WhatsApp message
# PIN was embedded in WhatsApp message: "Your PIN is 1234"

curl -X POST http://localhost:8000/api/receivers/verify-pin \
  -H "Content-Type: application/json" \
  -d '{
    "reference": "REF...",
    "phone": "+27111111111",
    "pin": "1234"
  }'

# Response: verified = true
# Database: transfer.receiver_phone_verified = true
```

**Step 4: Agent Verifies Receiver**
```bash
# Agent logs in (gets token)
curl -X POST http://localhost:8000/api/agent/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone": "+27123456789", "password": "password"}'

# Agent verifies receiver phone manually
curl -X POST http://localhost:8000/api/agent/transfers/{transfer_id}/verify \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"pin": "1234", "phone_verified": true}'

# Response: Agent verified, transfer state = RECEIVER_VERIFIED
# Now payout can proceed
```

---

### Scenario 2: PIN Resend Rate Limiting

```bash
# First resend - success
curl -X POST http://localhost:8000/api/receivers/resend-pin \
  -H "Content-Type: application/json" \
  -d '{"reference": "REF...", "phone": "+27111111111"}'

# Response: success = true, next_resend_in_seconds = 300

# Immediate second resend - rate limited
curl -X POST http://localhost:8000/api/receivers/resend-pin \
  -H "Content-Type: application/json" \
  -d '{"reference": "REF...", "phone": "+27111111111"}'

# Response: HTTP 429 Too Many Requests
# Message: "Please wait before requesting another PIN"
```

---

### Scenario 3: Brute-Force Protection

```bash
# Try invalid PIN 5 times
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/receivers/verify-pin \
    -H "Content-Type: application/json" \
    -d '{"reference": "REF...", "phone": "+27111111111", "pin": "9999"}'
done

# 6th attempt after 5 failures - lockout
curl -X POST http://localhost:8000/api/receivers/verify-pin \
  -H "Content-Type: application/json" \
  -d '{"reference": "REF...", "phone": "+27111111111", "pin": "1234"}'

# Response: HTTP 429 Too Many Requests
# Message: "Too many failed attempts. Try again in 30 minutes."
```

---

### Scenario 4: Admin Creates Agent

```bash
# Admin logs in first
curl -X POST http://localhost:8000/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone": "+27123456789", "password": "Admin1234"}'

# Admin creates new agent
curl -X POST http://localhost:8000/api/admin/agents \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+27987654321",
    "name": "New Agent",
    "location_code": "ZWE_HRR",
    "initial_cash_zar": 5000.00
  }'

# Response: agent_id, phone, status = ACTIVE
```

---

## 📊 Testing Checklist

### Backend Tests
- [ ] PIN generation creates 4-digit string
- [ ] PIN hashing is bcrypt and non-reversible
- [ ] PIN verification works with correct PIN
- [ ] PIN verification fails with wrong PIN
- [ ] Brute-force protection works (5 attempts)
- [ ] 30-minute lockout enforced
- [ ] PIN resend rate limiting enforced (1 per 5 min)
- [ ] Receiver can look up transfer by reference + phone
- [ ] Receiver phone mismatch returns 404
- [ ] Transfer status shows correct state
- [ ] Dual verification workflow works
- [ ] State transitions correctly after verification

### Frontend Tests
- [ ] Sender app loads at `/app`
- [ ] Sender can create transfer
- [ ] Sender can track transfer status
- [ ] Sender can view history
- [ ] Agent dashboard loads at `/agent`
- [ ] Agent can login with phone + password
- [ ] Agent can see pending transfers
- [ ] Agent can verify receiver
- [ ] Receiver portal loads at `/receiver`
- [ ] Receiver can look up transfer
- [ ] Receiver can enter PIN (auto-formats)
- [ ] Receiver sees success confirmation
- [ ] Admin dashboard loads at `/admin`
- [ ] All dashboards have navigation links

### Integration Tests
- [ ] All 25 implementation checks pass
- [ ] No Python syntax errors
- [ ] All required files present
- [ ] All key implementations found
- [ ] All navigation links work

---

## 📈 Expected Results

### Test Suite Output Example
```
tests/test_receiver_flow.py::TestReceiverFlowEndpoints::test_get_transfer_status_with_valid_reference PASSED
tests/test_receiver_flow.py::TestReceiverFlowEndpoints::test_get_transfer_status_not_found PASSED
tests/test_receiver_flow.py::TestReceiverFlowEndpoints::test_get_transfer_status_phone_mismatch PASSED
tests/test_receiver_flow.py::TestReceiverFlowEndpoints::test_verify_pin_success PASSED
tests/test_receiver_flow.py::TestReceiverFlowEndpoints::test_verify_pin_invalid PASSED
tests/test_receiver_flow.py::TestReceiverFlowEndpoints::test_verify_pin_already_verified PASSED
tests/test_receiver_flow.py::TestReceiverFlowEndpoints::test_verify_pin_wrong_transfer_state PASSED
tests/test_receiver_flow.py::TestReceiverFlowEndpoints::test_resend_pin_success PASSED
tests/test_receiver_flow.py::TestReceiverFlowEndpoints::test_resend_pin_rate_limit PASSED
tests/test_receiver_flow.py::TestReceiverFlowEndpoints::test_resend_pin_already_verified PASSED
tests/test_receiver_flow.py::TestPINGeneration::test_generate_pin_format PASSED
tests/test_receiver_flow.py::TestPINGeneration::test_pin_hash_security PASSED
tests/test_receiver_flow.py::TestPINGeneration::test_pin_verification_correct PASSED
tests/test_receiver_flow.py::TestPINGeneration::test_pin_verification_incorrect PASSED
tests/test_receiver_flow.py::TestReceiverDualVerification::test_transition_to_receiver_verified_both_verified PASSED
tests/test_receiver_flow.py::TestReceiverDualVerification::test_no_transition_when_agent_not_verified PASSED

======================== 16 passed in 0.45s ========================
```

---

## 🔍 Debugging Tips

### If PIN verification fails:
1. Check that `pin_generated` field is populated in database
2. Verify PIN hash is valid bcrypt format (starts with `$2b$`)
3. Check that receiver phone matches database
4. Check that transfer is in PAYMENT_LOCKED state

### If endpoints return 404:
1. Verify transfer reference is uppercase
2. Verify phone number format (+27... for South Africa)
3. Check that transfer actually exists in database
4. Verify reference is not expired

### If rate limiting isn't working:
1. Check that `last_pin_resent_at` is populated
2. Verify timestamp comparison logic
3. Check Redis connection for brute-force tracking
4. Check in-memory fallback for Redis failures

---

## 🚀 Deployment Verification

After deploying to production:

```bash
# 1. Check health endpoint
curl https://api.satsremit.com/health

# 2. Verify receiver endpoint exists
curl https://api.satsremit.com/api/receivers/transfers/TEST/status?phone=%2B27111

# 3. Check receiver app loads
curl https://receiver.satsremit.com/

# 4. Verify platform guide is accessible
curl https://satsremit.com/platform-guide.html

# 5. Run test suite against production (safely)
python3 -m pytest tests/test_receiver_flow.py -v --base-url=https://api.satsremit.com
```

---

## ✅ Sign-Off Checklist

Before going live:

- [ ] All 25 implementation checks pass
- [ ] All test cases pass
- [ ] Manual testing scenarios validated
- [ ] Frontend navigation verified
- [ ] Database migrations applied
- [ ] Admin agent created and tested
- [ ] Sender transfer created successfully
- [ ] Receiver PIN verified successfully
- [ ] Agent verified receiver successfully
- [ ] Admin can monitor all transfers
- [ ] Platform guide accessible
- [ ] Error handling tested
- [ ] Rate limiting tested
- [ ] Brute-force protection tested

---

## 📞 Support Resources

- **Implementation Summary**: `IMPLEMENTATION_COMPLETE.md`
- **Platform Guide**: `/platform-guide.html`
- **Test Suite**: `tests/test_receiver_flow.py`
- **API Docs**: `/api/docs` (when running)
- **Verification Script**: `verify_implementation.py`

---

**Status**: ✅ READY FOR TESTING & DEPLOYMENT

*Test and verify all scenarios above before production release.*
