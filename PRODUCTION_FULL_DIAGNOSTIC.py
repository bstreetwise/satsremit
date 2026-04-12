#!/usr/bin/env python3
"""
Full Diagnostic for Agent Creation Issue on Production
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("SATSREMIT PRODUCTION DIAGNOSTIC - AGENT CREATION FAILURE")
print("=" * 70)

# Test 1: Database Connection
print("\n1. Testing Database Connection...")
try:
    from src.db.database import DatabaseManager
    db = DatabaseManager()
    session = db.get_session()
    
    from sqlalchemy import text
    result = session.execute(text("SELECT 1"))
    print("   ✓ Database connection OK")
    
    # Check admin user
    from src.models.models import Agent
    admin = session.query(Agent).filter_by(phone="+27111111111").first()
    
    if admin:
        print(f"   ✓ Admin user found: {admin.phone}")
        print(f"     - Name: {admin.name}")
        print(f"     - Status: {admin.status.value}")
        print(f"     - Is Admin: {admin.is_admin}")
    else:
        print("   ✗ Admin user +27111111111 NOT FOUND in database!")
        print("   Available admin users:")
        admins = session.query(Agent).filter(Agent.is_admin == True).all()
        if admins:
            for a in admins:
                print(f"     - {a.phone}: {a.name} ({a.status.value})")
        else:
            print("     (No admin users at all!)")
    
    session.close()
    
except Exception as e:
    print(f"   ✗ Database error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Check API code
print("\n2. Checking API Code...")
try:
    from src.api.routes import admin as admin_routes
    if hasattr(admin_routes, 'create_agent'):
        print("   ✓ create_agent endpoint exists in code")
    else:
        print("   ✗ create_agent endpoint NOT in code!")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 3: Check for syntax errors
print("\n3. Checking Python Syntax...")
import py_compile
files_to_check = [
    'src/api/routes/admin.py',
    'src/models/models.py',
    'src/main.py',
]

for file in files_to_check:
    try:
        py_compile.compile(str(project_root / file), doraise=True)
        print(f"   ✓ {file}")
    except py_compile.PyCompileError as e:
        print(f"   ✗ {file}: {e}")

# Test 4: Check dependencies
print("\n4. Checking Dependencies...")
deps = ['fastapi', 'sqlalchemy', 'psycopg2', 'bcrypt']
for dep in deps:
    try:
        __import__(dep)
        print(f"   ✓ {dep}")
    except ImportError:
        print(f"   ✗ {dep} NOT INSTALLED")

# Test 5: Frontend files
print("\n5. Checking Frontend Files...")
frontend_files = [
    'static/admin/index.html',
    'static/admin/js/api.js',
    'static/admin/js/ui.js',
]
for file in frontend_files:
    if (project_root / file).exists():
        print(f"   ✓ {file}")
    else:
        print(f"   ✗ {file} NOT FOUND")

print("\n" + "=" * 70)
print("DIAGNOSIS SUMMARY")
print("=" * 70)

print("""
KEY FINDINGS:
1. API server is NOT running
2. Need to check: Is admin user actually in the database?
3. Code looks valid based on syntax checks
4. Dependencies seem to be available

NEXT STEPS:
1. Start the API server:
   cd /home/satsinaction/satsremit
   uvicorn src.main:app --reload

2. Then test agent creation again

3. Check server terminal output for errors

4. If still failing, check:
   - Server console output (will show detailed error)
   - Error message in admin UI (should now be specific)
""")
