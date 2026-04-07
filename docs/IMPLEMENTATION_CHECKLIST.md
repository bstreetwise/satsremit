# Implementation Checklist for Phase 1 MVP

## Sprint 1: Core Services (Week 1-2)

### Transfer Service
- [ ] `create_transfer()` - Main transfer creation logic
  - [ ] Validate sender/receiver phone format
  - [ ] Check amount is in 100-500 ZAR range
  - [ ] Verify agent exists and is ACTIVE
  - [ ] Check agent has sufficient cash balance
  - [ ] Calculate ZAR → sats conversion
  - [ ] Generate unique reference (REF-XXXXX)
  - [ ] Save transfer to DB (INITIATED state)
  - [ ] Return transfer object with details
- [ ] `verify_transfer()` - Agent verification
  - [ ] Find transfer by ID
  - [ ] Validate PIN matches
  - [ ] Validate phone number matches
  - [ ] Check transfer state is PAYMENT_LOCKED
  - [ ] Transition to RECEIVER_VERIFIED
  - [ ] Save to transfer_history
- [ ] `confirm_payout()` - Agent confirms cash paid
  - [ ] Find transfer by ID
  - [ ] Verify agent is the assigned agent
  - [ ] Check state is RECEIVER_VERIFIED
  - [ ] Transition to PAYOUT_EXECUTED
  - [ ] Trigger settlement background task
- [ ] `refund_transfer()` - For failed verifications
  - [ ] Find transfer by ID
  - [ ] Create refund event
  - [ ] Release LND invoice hold
  - [ ] Transition to REFUNDED
  - [ ] Notify sender

### LND Service (Lightning Network)
- [ ] `create_hold_invoice()` - Generate hold invoice
  - [ ] Connect to LND REST API
  - [ ] Calculate sats from ZAR amount
  - [ ] Create hold invoice with 15 min TTL
  - [ ] Store preimage encrypted in DB
  - [ ] Return payment_request string
- [ ] `settle_invoice()` - Settle after verification
  - [ ] Retrieve stored preimage
  - [ ] Settle invoice with LND
  - [ ] Verify settlement success
  - [ ] Update transfer state to SETTLED
- [ ] `cancel_invoice()` - Cancel hold invoice
  - [ ] Cancel invoice with LND
  - [ ] Release any locked sats
  - [ ] Clean up preimage from DB

### Rate Service
- [ ] `get_exchange_rate()` - Fetch current rates
  - [ ] Check Redis cache first
  - [ ] If expired, fetch from external source (Coingecko)
  - [ ] Cache result for 5 minutes
  - [ ] Return decimal rate
- [ ] `lock_rate()` - Lock rate for transfer
  - [ ] Get current rate
  - [ ] Store with timestamp
  - [ ] Return locked rate
- [ ] `convert_zar_to_sats()` - Convert currency
  - [ ] Get rate at invoice generation
  - [ ] Calculate: ZAR amount / rate = sats
  - [ ] Round to satoshi precision
  - [ ] Return amount in sats

### Notification Service (Twilio)
- [ ] `send_pin_to_receiver()` - Send PIN via WhatsApp
  - [ ] Generate 4-digit PIN
  - [ ] Format message with transfer details
  - [ ] Send via Twilio WhatsApp API
  - [ ] Log delivery status
  - [ ] Store PIN hash in DB
- [ ] `notify_agent()` - Alert agent of pending transfer
  - [ ] Send via WhatsApp or SMS
  - [ ] Include receiver name and amount
  - [ ] Include unique transfer reference
- [ ] `notify_sender()` - Confirm to sender
  - [ ] Send when transfer complete
  - [ ] Include receiver name and status

## Sprint 2: API Routes (Week 2-3)

### Public Routes
- [ ] `POST /api/transfers` - Create transfer
  - [ ] Validate request schema
  - [ ] Call TransferService.create_transfer()
  - [ ] Return TransferResponse with invoice
- [ ] `GET /api/transfers/{id}` - Get transfer status
  - [ ] Find transfer by ID
  - [ ] Return non-sensitive fields
- [ ] `GET /api/agent/locations` - List agents
  - [ ] Query all ACTIVE agents
  - [ ] Return list with location + phone

### Agent Routes
- [ ] `POST /api/agent/auth/login` - Agent login
  - [ ] Validate phone + password
  - [ ] Hash password check
  - [ ] Generate JWT token
  - [ ] Return token + agent info
- [ ] `GET /api/agent/balance` - Agent balance
  - [ ] Get authenticated agent
  - [ ] Return cash balance + commission
- [ ] `GET /api/agent/transfers` - Pending transfers
  - [ ] Query transfers with state=PAYMENT_LOCKED
  - [ ] Filter by assigned agent
  - [ ] Return list of pending transfers
- [ ] `POST /api/agent/transfers/{id}/verify` - Verify receiver
  - [ ] Get authenticated agent
  - [ ] Validate PIN
  - [ ] Call TransferService.verify_transfer()
  - [ ] Return result
- [ ] `POST /api/agent/transfers/{id}/confirm-payout` - Confirm payout
  - [ ] Get authenticated agent
  - [ ] Call TransferService.confirm_payout()
  - [ ] Return confirmation
- [ ] `GET /api/agent/settlements` - Settlement history
  - [ ] Get authenticated agent
  - [ ] List all settlements for agent
- [ ] `POST /api/agent/settlement/{id}/confirm` - Confirm settlement
  - [ ] Validate payment method
  - [ ] Record payment reference
  - [ ] Mark settlement CONFIRMED

### Admin Routes
- [ ] `POST /api/admin/agent/add` - Create agent
  - [ ] Validate request
  - [ ] Hash password
  - [ ] Save to DB
  - [ ] Return agent info
- [ ] `GET /api/admin/agent/{id}/balance` - Agent balance check
  - [ ] Query agent + settlements
  - [ ] Calculate totals
- [ ] `POST /api/admin/agent/{id}/advance` - Record cash advance
  - [ ] Update agent cash_balance
  - [ ] Create audit log
- [ ] `GET /api/admin/transfers` - Transfer list
  - [ ] Support filtering by state, date range
  - [ ] Paginate results
  - [ ] Return full transfer data
- [ ] `GET /api/admin/volume` - Platform metrics
  - [ ] Calculate daily/weekly/monthly volume
  - [ ] Sum fees collected

### Webhook Routes
- [ ] `POST /api/webhooks/lnd/invoice-settled` - LND callback
  - [ ] Verify webhook signature
  - [ ] Find transfer by invoice_hash
  - [ ] Validate amount
  - [ ] Transition to PAYMENT_LOCKED
  - [ ] Send PIN to receiver
  - [ ] Alert agent
- [ ] `POST /api/webhooks/lnd/invoice-expired` - Invoice expiry
  - [ ] Find transfer by invoice_hash
  - [ ] Transition to REFUNDED
  - [ ] Notify sender

## Sprint 3: Testing & Polish (Week 3-4)

### Unit Tests
- [ ] TransferService tests (80%+ coverage)
  - [ ] test_create_transfer_success
  - [ ] test_create_transfer_invalid_amount
  - [ ] test_create_transfer_insufficient_agent_balance
  - [ ] test_verify_transfer_invalid_pin
  - [ ] test_verify_transfer_success
  - [ ] test_confirm_payout_success
  - [ ] test_refund_transfer
- [ ] LNDService tests
  - [ ] test_create_hold_invoice
  - [ ] test_settle_invoice
  - [ ] test_cancel_invoice
- [ ] RateService tests
  - [ ] test_get_exchange_rate
  - [ ] test_cache_working
  - [ ] test_convert_zar_to_sats

### Integration Tests
- [ ] test_complete_transfer_flow
  - [ ] Create transfer
  - [ ] Agent verifies
  - [ ] Agent confirms payout
  - [ ] Settlement checks
- [ ] test_webhook_invoice_settled
  - [ ] LND webhook → Transfer state change
  - [ ] PIN notification sent
  - [ ] Agent notification sent

### API Route Tests
- [ ] Each endpoint with:
  - [ ] Valid request → 200 response
  - [ ] Invalid request → 400 response
  - [ ] Missing auth → 401 response
  - [ ] Invalid state → 422 response

### Documentation
- [ ] Update README with:
  - [ ] API endpoint examples
  - [ ] Error codes and meanings
  - [ ] Integration instructions
- [ ] Create DEPLOYMENT.md
- [ ] Add postman collection
- [ ] Setup API docs auto-generation

## Sprint 4: Deployment Preparation (Week 4)

### Infrastructure
- [ ] Create Dockerfile for API
- [ ] Create docker-compose.prod.yml
- [ ] Setup PostgreSQL backups
- [ ] Redis persistence config
- [ ] SSL/TLS certificate setup

### Security Hardening
- [ ] Rate limiting middleware
- [ ] CSRF protection
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention checks
- [ ] Secrets rotation procedure

### Monitoring & Logging
- [ ] Structured logging setup
- [ ] Error monitoring integration
- [ ] Database query logging
- [ ] API request/response logging
- [ ] Alert rules for critical errors

### Testing & Validation
- [ ] Full regression test suite
- [ ] Load testing (100+ transfers/hour)
- [ ] Failure scenario testing
- [ ] Backup/restore testing
- [ ] Security audit checklist

## Priority Order

### Critical Path (Must Have)
1. Transfer creation & state machine
2. LND integration (hold invoices)
3. Agent verification flow
4. Payout confirmation & settlement
5. Basic API routes
6. Testnet testing

### Important (Should Have)
7. Comprehensive tests
8. Error handling & logging
9. Notification system
10. Admin routes for monitoring

### Nice to Have (Could Have)
11. Dashboard/metrics
12. Advanced authentication
13. Rate limiting
14. Monitoring integration

## Definition of Done

- [ ] Code passes linting
- [ ] >80% test coverage
- [ ] All docstrings present
- [ ] Type hints on all functions
- [ ] Database schema consistent
- [ ] No hardcoded values/secrets
- [ ] Error messages informative
- [ ] Performance acceptable (<500ms p95)

## Success Metrics (Phase 1 Complete)

- ✅ Single transfer flow working end-to-end
- ✅ 100+ transfers successfully processed on testnet
- ✅ >95% settlement success rate
- ✅ <5 min average time to payout
- ✅ Zero critical bugs in production
- ✅ All API endpoints documented
- ✅ All code reviewed and tested

---

**Target**: 4-6 weeks to Phase 1 completion with focused team  
**Next**: Begin Sprint 1 with TransferService and LNDService implementation
