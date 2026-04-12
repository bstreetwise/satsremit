#!/usr/bin/env python3
"""
Fix 500 Error: Agent Creation
Improved error handling in backend to show actual error message
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("AGENT CREATION 500 ERROR - ANALYSIS")
print("=" * 70)

print("\n✓ Backend Fix Applied:")
print("  - Added input validation for phone field")
print("  - Added validation for cash amount")
print("  - Added safe password hashing with error handling")
print("  - Improved error messages (now shows actual error, not generic 500)")
print("  - Added detailed logging with tracebacks")

print("\n✓ Frontend Already Handles Errors:")
print("  - Error messages displayed to user")
print("  - Shows actual API error detail in alert")

print("\n" + "=" * 70)
print("COMMON 500 ERRORS - CAUSES & FIXES")
print("=" * 70)

errors = [
    {
        "error": "Missing Agent model field",
        "cause": "Database schema missing required column",
        "fix": "Run database migration: python3 scripts/init_db.py",
        "sign": "KeyError or missing field error in logs"
    },
    {
        "error": "Password hashing failure",
        "cause": "bcrypt library issue or too-long password",
        "fix": "Reinstall bcrypt: pip install --upgrade bcrypt",
        "sign": "bcrypt error in logs"
    },
    {
        "error": "Decimal conversion error",
        "cause": "Initial cash sent as string or invalid value",
        "fix": "Ensure initial cash is number in form",
        "sign": "ValueError: Invalid literal for Decimal"
    },
    {
        "error": "Database constraint violation",
        "cause": "Unique constraint or foreign key error",
        "fix": "Check database integrity",
        "sign": "IntegrityError in logs"
    },
    {
        "error": "Database connection failed",
        "cause": "DATABASE_URL invalid or DB unreachable",
        "fix": "Check DATABASE_URL in .env and verify DB is running",
        "sign": "OperationalError or connection refused"
    },
]

for i, err in enumerate(errors, 1):
    print(f"\n{i}. {err['error']}")
    print(f"   Cause: {err['cause']}")
    print(f"   Fix: {err['fix']}")
    print(f"   Sign: {err['sign']}")

print("\n" + "=" * 70)
print("WHAT TO DO NOW")
print("=" * 70)

steps = """
1. RESTART API SERVER (with improved error handling)
   - Stop current server (Ctrl+C)
   - Restart: uvicorn src.main:app --reload
   - New code includes better error messages

2. TRY CREATING AGENT AGAIN
   - Go to admin dashboard
   - Try creating an agent
   - Check DevTools -> Network tab -> /api/admin/agents response
   - Now should see detailed error instead of generic "500"

3. CHECK ERROR MESSAGE
   - If still 500, find error in server logs
   - Look for line with "Agent creation failed"
   - Copy full error message

4. RESOLVE BASED ON ERROR
   - Match error message to list above
   - Apply corresponding fix
   - Retry

5. IF STILL FAILING
   - Run: python3 -m py_compile src/api/routes/admin.py
   - Verify no syntax errors
   - Check: pip list | grep -E "bcrypt|sqlalchemy"
   - Verify dependencies installed
"""

print(steps)

print("\n" + "=" * 70)
print("TO CHECK SERVER LOGS (if you have SSH access)")
print("=" * 70)

print("""
# Check last errors
tail -50 /var/log/api/production.log

# Follow real-time
tail -f /var/log/api/production.log

# Look for "Agent creation failed" line
grep "Agent creation failed" /var/log/api/production.log
""")

print("\n" + "=" * 70)
print("FILES MODIFIED")
print("=" * 70)

print("""
✓ src/api/routes/admin.py
  - Added input validation (phone, cash)
  - Added safe password hashing
  - Improved error messages
  - Better error logging with tracebacks
  - Returns detailed error info instead of generic "500"
""")

print("\n" + "=" * 70)
print("NEXT STEP: Restart server and try again")
print("=" * 70)
