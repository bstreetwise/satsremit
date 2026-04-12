#!/usr/bin/env python3
"""
Production Diagnostic: Agent Creation Failure on Live System
Run this to gather information about the error
"""

diagnostic_info = """
=============================================================
PRODUCTION DIAGNOSTIC: Agent Creation Error
=============================================================

To help diagnose the issue on https://satsremit.com/admin/, 
please provide the following information:

1. ERROR MESSAGE
   ================
   When you click "Create Agent", what error do you see?
   
   Options:
   a) Network error (red error in admin dashboard)
   b) Success message but agent doesn't appear
   c) Form won't submit
   d) "Unauthorized" error
   e) Other: ___________________
   
   Please copy the exact error message here:
   _______________________________________________
   _______________________________________________

2. BROWSER CONSOLE ERROR (Press F12)
   ================
   
   a) Open https://satsremit.com/admin/
   b) Press F12 (Dev Tools)
   c) Go to "Console" tab
   d) Try to create agent
   e) Look for red error message
   f) Copy entire error message:
   
   _______________________________________________
   _______________________________________________

3. NETWORK TAB (Press F12)
   ================
   
   a) Press F12 (Dev Tools)
   b) Go to "Network" tab
   c) Clear history (circle with slash)
   d) Try to create agent
   e) Look for red request (failed)
   f) Click the request to "/api/admin/agents"
   g) Go to "Response" tab
   h) Copy the response:
   
   _______________________________________________
   _______________________________________________

4. FORM DATA
   ================
   
   What values did you enter?
   
   Agent Phone: ___________________
   Agent Name: ____________________
   Location: ______________________
   Initial Cash (ZAR): _____________

5. WHEN DID IT START?
   ================
   
   a) First time creating agent
   b) Was working, then stopped
   c) Intermittent (sometimes works, sometimes fails)

6. ADMIN LOGIN
   ================
   
   a) Can you login to admin dashboard?
   b) Do you see "Agents" section?
   c) Can you see existing agents list?

=============================================================
COMMON ISSUES & QUICK CHECKS
=============================================================

1. IF ERROR: "Unauthorized"
   Fix: Logout and login again (token might be expired)

2. IF ERROR: "Agent phone already registered"
   Fix: Use a different phone number

3. IF ERROR: "Invalid phone format"
   Fix: Phone must start with +, example: +263712345678

4. IF ERROR: "Initial cash too low"
   Fix: Minimum cash is 100 ZAR

5. IF ERROR: "Database connection failed"
   Fix: Contact devops to check database

6. IF ERROR: "Internal server error (500)"
   Fix: Check server logs for actual error

=============================================================
DEBUGGING STEPS
=============================================================

Step 1: Test with curl (if you have access)
--------
TOKEN=$(curl -s -X POST https://satsremit.com/api/admin/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{
    "phone": "+263712000000",
    "password": "YOUR_PASSWORD"
  }' | jq -r '.token')

curl -X POST https://satsremit.com/api/admin/agents \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "phone": "+263712345678",
    "name": "Test Agent",
    "location_code": "harare",
    "initial_cash_zar": 1000
  }'

Step 2: Check server logs
--------
ssh satsremit.com
tail -f /var/log/api/production.log

Step 3: Test database connection
--------
psql $PRODUCTION_DATABASE_URL -c "SELECT COUNT(*) FROM agents"

=============================================================
"""

print(diagnostic_info)

# Also try to check common issues programmatically
print("\n" + "=" * 60)
print("POSSIBLE CAUSES (in order of likelihood):")
print("=" * 60)

causes = [
    (1, "Agent phone already exists", "Try different phone number"),
    (2, "Admin token expired", "Logout and login again"),
    (3, "Database connection error", "Check database is running"),
    (4, "Invalid phone format", "Ensure phone starts with +"),
    (5, "Initial cash below minimum", "Minimum is 100 ZAR"),
    (6, "API endpoint not responding", "Check if server is running"),
    (7, "Agent creation endpoint broken", "Check code has no errors"),
    (8, "Database permission issue", "Check DB user has INSERT rights"),
]

for idx, cause, fix in causes:
    print(f"\n{idx}. {cause}")
    print(f"   Fix: {fix}")

print("\n" + "=" * 60)
print("Next: Provide the information from section 1-6 above")
print("=" * 60)
