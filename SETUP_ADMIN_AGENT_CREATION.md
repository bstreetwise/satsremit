# 🚀 Complete Setup Guide: Get Agent Creation Working

## Status: ✅ Code Validated
All backend and frontend code is present and valid. The issue is **setup/configuration related**, not code.

---

## Quick Start (5 Minutes)

### Step 1: Create Admin User (1 min)
```bash
cd /home/satsinaction/satsremit
python3 scripts/create_admin.py
# When prompted:
#   Phone: +263712000000
#   Password: Admin1234
#   Name: Admin User
```

**Output should be:**
```
✓ Admin user created successfully!
  Phone: +263712000000
  Password: Admin1234
```

### Step 2: Start API Server (1 min)
```bash
cd /home/satsinaction/satsremit
uvicorn src.main:app --reload
```

**Wait for:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 3: Login to Admin Dashboard (1 min)
1. Open browser: `http://localhost:8000/admin`
2. Phone: `+263712000000`
3. Password: `Admin1234`
4. Click "Login"

**Should see: Admin dashboard with Agents section**

### Step 4: Create Your First Agent (2 min)
1. Click "Agents" section
2. Click "Register New Agent" button
3. Fill in form:
   - **Agent Phone**: `+263712345678`
   - **Agent Name**: `John Harare`
   - **Location**: `harare`
   - **Initial Cash (ZAR)**: `1000`
4. Click "Create Agent"

**Expected Result:**
- ✅ Success message appears
- ✅ Agent appears in agents table
- ✅ Status shows "ACTIVE"

---

## Detailed Troubleshooting

### Issue: "Admin user not found" when logging in

**Symptoms:**
- Login fails
- Error: "Invalid credentials"
- Cannot access admin dashboard

**Solution:**
```bash
# Create admin user
python3 scripts/create_admin.py

# Follow interactive prompts
# Default credentials suggested:
# Phone: +263712000000
# Password: Admin1234
```

**Verify it worked:**
```bash
# Try logging in again at http://localhost:8000/admin
```

---

### Issue: API server not responding (404/500 errors)

**Symptoms:**
- Admin dashboard loads but agent creation fails
- Network tab shows red X on /api/admin/agents
- "Cannot POST /api/admin/agents"

**Solution:**
```bash
# Make sure the API server is running
ps aux | grep uvicorn

# If not running, start it:
cd /home/satsinaction/satsremit
uvicorn src.main:app --reload

# Wait for "Uvicorn running on http://127.0.0.1:8000"
```

---

### Issue: Agent creation form doesn't submit

**Symptoms:**
- Click "Create Agent" nothing happens
- No error message
- No Network request in DevTools

**Solution:**

1. **Check form validation:**
   ```
   - Ensure all fields are filled
   - Phone: Must start with +
   - Initial Cash: Minimum 100 ZAR
   - Location: Must select from dropdown
   ```

2. **Check browser console (F12):**
   - Open DevTools
   - Go to "Console" tab
   - Try creating agent again
   - Look for red error message
   - Screenshot and report error

3. **Check Network tab (F12):**
   - Click Network tab
   - Clear (click circle with slash)
   - Try creating agent
   - Look for request to `/api/admin/agents`
   - Click it
   - Check "Response" tab for error message

---

### Issue: "Unauthorized - Please login again" error

**Symptoms:**
- Was able to login
- Agent creation shows unauthorized error
- Token might be expired

**Solution:**
```
1. Open admin dashboard
2. Open browser Console (F12)
3. Run: localStorage.removeItem('admin_token')
4. Refresh page (F5)
5. Login again
6. Try agent creation
```

---

### Issue: No active agents showing in dashboard

**Symptoms:**
- Agents table empty
- Only see "Loading agents..." message
- No agents appear even after creation

**Solution:**

1. **Check if API is returning agents:**
   ```bash
   # Test the endpoint directly
   curl -X GET http://localhost:8000/api/admin/agents \
     -H "Authorization: Bearer YOUR_TOKEN"
   # Should return JSON list of agents
   ```

2. **Check if agents were created:**
   - Try creating an agent again
   - Check for success message
   - Refresh page
   - Agents should appear

3. **Clear browser cache:**
   - Press F12
   - Right-click refresh button
   - Select "Empty cache and hard refresh"
   - Try again

---

## Complete Setup from Scratch

If you're setting up for the first time:

### 1. Database Setup
```bash
cd /home/satsinaction/satsremit

# Create admin user
python3 scripts/create_admin.py

# Follow prompts and use:
# Phone: +263712000000
# Password: Admin1234
```

### 2. Start Backend
```bash
# Terminal 1: Start API server
cd /home/satsinaction/satsremit
uvicorn src.main:app --reload

# Wait for: "Uvicorn running on http://127.0.0.1:8000"
```

### 3. Access Frontend
```bash
# Terminal 2: (Or just open in browser)
# Visit: http://localhost:8000/admin

# Login:
# Phone: +263712000000
# Password: Admin1234
```

### 4. Test Agent Creation
```bash
# In admin dashboard:
1. Go to "Agents" section
2. Click "Register New Agent"
3. Fill form:
   - Phone: +263712345678
   - Name: Test Agent
   - Location: harare
   - Initial Cash: 1000
4. Click "Create Agent"
5. Should see success message
6. Agent appears in table
```

---

## API Testing (Manual)

If you want to test the API directly:

### 1. Get Admin Token
```bash
curl -X POST http://localhost:8000/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+263712000000",
    "password": "Admin1234"
  }'

# Response:
# {"token":"eyJ0eXAiOiJKV1QiLCJhbGc..."}
```

### 2. Create Agent (replace TOKEN)
``bash
TOKEN="your_token_from_above"

curl -X POST http://localhost:8000/api/admin/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+263712345678",
    "name": "Test Agent",
    "location_code": "harare",
    "initial_cash_zar": 1000.00
  }'

# Response:
# {
#   "agent_id": "...",
#   "phone": "+263712345678",
#   "name": "Test Agent",
#   "status": "ACTIVE",
#   "cash_balance_zar": 1000.00
# }
```

### 3. List Agents
```bash
curl -X GET http://localhost:8000/api/admin/agents \
  -H "Authorization: Bearer $TOKEN"

# Response is list of all agents
```

---

## Checklist: Admin & Agent Setup

- [ ] Admin user created (`+263712000000`)
- [ ] Admin can login to `/admin`
- [ ] API server running on http://localhost:8000
- [ ] Admin dashboard loads without errors
- [ ] "Agents" section visible in left sidebar
- [ ] "Register New Agent" button visible
- [ ] Can fill and submit agent creation form
- [ ] Success message appears after creation
- [ ] New agent appears in agents table
- [ ] Agent status shows "ACTIVE"
- [ ] Can see agent details (phone, name, location, balance)

---

## Files Involved

| File | Purpose |
|------|---------|
| `scripts/create_admin.py` | Create admin user in database |
| `scripts/init_db.py` | Initialize entire database schema |
| `src/api/routes/admin.py` | Backend admin endpoints |
| `src/main.py` | FastAPI app initialization |
| `static/admin/index.html` | Admin UI |
| `static/admin/js/api.js` | API client methods |
| `static/admin/js/app.js` | Frontend logic |
| `.env` | Database configuration |

---

## Common Errors & Fixes

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'psycopg2'` | Install dependencies: `pip install -r requirements.txt` |
| `No module named 'celery'` | Install: `pip install celery` |
| `Cannot connect to database` | Check DATABASE_URL in .env and PostgreSQL is running |
| `Admin user already exists` | Use `--force` flag or provide different phone |
| `401 Unauthorized` | Logout and login again, or token expired |
| `400 Bad Request: Agent phone already registered` | Phone already used, try different number |
| `400 Bad Request: Invalid credentials` | Admin phone/password wrong, check .env |
| `Agent creation success but agent doesn't appear` | Refresh page or clear browser cache |

---

## Next Steps After Setup

Once agent creation is working:

1. **Create multiple test agents:**
   - Agent 1: `+263712345678` (Harare)
   - Agent 2: `+263782345678` (Bulawayo)
   - Agent 3: `+263722345678` (Mutare)

2. **Test sender flow:**
   - Go to `/app` (Sender dashboard)
   - Create a test transfer
   - Make sure agents appear in dropdown

3. **Test complete flow:**
   - Sender creates transfer
   - Agent accepts/verifies receiver
   - Receiver enters PIN
   - Agent approves payout

4. **Check all dashboards:**
   - `/app` - Sender view
   - `/agent` - Agent view
   - `/admin` - Admin view
   - `/receiver` - Receiver view (with reference + PIN)

---

## Support

If still having issues after following this guide:

1. **Collect diagnostic info:**
   ```bash
   python3 diagnose_agent_issue.py
   ```

2. **Check server logs:**
   - Look at terminal running `uvicorn` for errors

3. **Check browser console:**
   - Press F12
   - Go to Console tab
   - Look for red errors

4. **Check API response:**
   - Press F12
   - Go to Network tab
   - Create agent
   - Click /api/admin/agents request
   - Check Response tab for error details

5. **Report with:**
   - Error message (screenshot)
   - API response (from Network tab)
   - Server logs (from terminal)
   - Browser console errors

---

**Date Updated**: April 11, 2026  
**Status**: Setup Guide Complete  
**Tested**: Code validation passed, ready for deployment
