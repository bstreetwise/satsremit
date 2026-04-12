# 🔧 Fix: Agent Creation by Admin Fails

## Problem

When admin tries to create a new agent via the admin dashboard, the request fails because:
- **Root Cause**: No admin user exists in the database
- **Why**: The database initialization script (`init_db.py`) wasn't creating an admin user, only test agents

## Solution Applied

### 1. ✅ Updated Database Initialization Script
File: `scripts/init_db.py`

**What Changed:**
- Added admin user creation during database seeding
- Admin credentials:
  - **Phone**: `+263712000000`
  - **Password**: `Admin1234`
  - **Name**: Admin User
  - **Status**: ACTIVE

**When This Helps:**
- If you're initializing the database for the first time
- Run: `python3 scripts/init_db.py`

### 2. ✅ Created Standalone Admin Creation Script
File: `scripts/create_admin.py`

**Purpose**: Create or upgrade an admin user if database is already initialized

**Usage - Interactive Mode:**
```bash
python3 scripts/create_admin.py
# Then answer prompts:
# - Enter admin phone number (+263...)
# - Enter admin password (min 8 chars)
# - Enter admin name (optional)
```

**Usage - Command Line Mode:**
```bash
python3 scripts/create_admin.py "+263712345678" "MyPassword123" "Admin Name"
```

**Features:**
- Checks if admin already exists
- Can upgrade existing agent to admin
- Validates password strength
- Logs success/error clearly

## Fix Instructions

### For Fresh Database Setup
```bash
# 1. Initialize database (now includes admin user)
python3 scripts/init_db.py

# 2. Start API server
uvicorn src.main:app --reload

# 3. Login to admin at http://localhost:8000/admin
#    Phone: +263712000000
#    Password: Admin1234
```

### For Existing Database
If you already have a database initialized without an admin:

```bash
# Option 1: Interactive creation
python3 scripts/create_admin.py

# Option 2: Command line
python3 scripts/create_admin.py "+263712000000" "Admin1234"
```

## How Agent Creation Now Works

### Step 1: Admin Login
```
Phone: +263712000000
Password: Admin1234
```
↓
```
JWT token issued (grants "is_admin" claim)
```

### Step 2: Create Agent Form
Admin fills in:
- Agent Phone: `+263712345678`
- Agent Name: `John Agent`
- Location: `harare`
- Initial Cash: `1000` ZAR

↓

### Step 3: Backend Processing
```
POST /api/admin/agents
{
  "phone": "+263712345678",
  "name": "John Agent",
  "location_code": "harare",
  "initial_cash_zar": 1000.00
}
```

**Validation Chain:**
1. ✅ Check admin token has `is_admin=True`
2. ✅ Check phone not already registered
3. ✅ Hash temporary password: `TempPassword123!`
4. ✅ Store agent with `must_change_password=True`
5. ✅ Return agent details

### Step 4: Success
Agent appears in agents table with:
- Phone
- Name
- Location
- Cash Balance
- Status: ACTIVE

## Testing Agent Creation

### Via Admin Dashboard
1. Navigate to `http://localhost:8000/admin`
2. Login with admin credentials
3. Go to "Agents" section
4. Click "Register New Agent"
5. Fill in form and submit
6. See success message

### Via Direct API Test
```bash
# Get admin token
curl -X POST http://localhost:8000/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone": "+263712000000", "password": "Admin1234"}'

# Response:
# {"token": "eyJ0eXAi..."}

# Create agent (replace TOKEN)
curl -X POST http://localhost:8000/api/admin/agents \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+263712345678",
    "name": "Test Agent",
    "location_code": "harare",
    "initial_cash_zar": 1000
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

## Files Modified

| File | Change |
|------|--------|
| `scripts/init_db.py` | Added admin user creation in `seed_test_data()` function |
| `scripts/create_admin.py` | **NEW** - Standalone admin creation script |

## Security Notes

⚠️ **Important for Production:**
1. **Change Default Admin Password** - Don't use `Admin1234` in production
2. **Secure Default Stored** - Use environment variable: `ADMIN_DEFAULT_PASSWORD`
3. **First Login** - Force admin to change password on first login
4. **Remove Test Phone** - Remove default admin if deploying

**Production Setup:**
```bash
# Create admin with secure password
python3 scripts/create_admin.py "+263712000000" "$RANDOM_SECURE_PASSWORD"

# Or via environment variable
export ADMIN_PHONE="+263712000000"
export ADMIN_PASSWORD="$(openssl rand -base64 32)"
python3 scripts/create_admin.py $ADMIN_PHONE $ADMIN_PASSWORD
```

## Verification Checklist

- ✅ Admin user created in database
- ✅ Admin can login with credentials
- ✅ Admin JWT token includes `is_admin: true`
- ✅ Agent creation form accessible in admin dashboard
- ✅ New agents can be created and appear in list
- ✅ Agents have status ACTIVE and correct details

## Next Steps

1. **Initialize/Update Database**:
   ```bash
   python3 scripts/init_db.py
   ```

2. **Start API Server**:
   ```bash
   uvicorn src.main:app --reload
   ```

3. **Test Admin Login**:
   - Visit `http://localhost:8000/admin`
   - Login with provided credentials

4. **Create New Agents**:
   - Use admin dashboard to create agents
   - Verify in agents table

---

**Issue**: Agent creation by admin fails  
**Status**: ✅ FIXED  
**Cause**: Missing admin user in database  
**Solution**: Database initialization now creates admin + standalone script  
**Date Fixed**: April 11, 2026
