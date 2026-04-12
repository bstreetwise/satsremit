#!/usr/bin/env python3
"""
Diagnostic script: Check agent creation issue
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_issue():
    print("=" * 60)
    print("SatsRemit Agent Creation Diagnostic")
    print("=" * 60)
    
    # Test 1: Check schemas
    print("\n1. Checking schemas...")
    try:
        from src.api.schemas import AdminAgentCreateRequest
        print("   OK: Schemas importable")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False
    
    # Test 2: Check models
    print("\n2. Checking models...")
    try:
        from src.models.models import Agent, AgentStatus
        print("   OK: Models importable")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False
    
    # Test 3: Check routes
    print("\n3. Checking API routes...")
    try:
        from src.api.routes import admin
        print("   OK: Admin routes importable")
        if hasattr(admin, 'create_agent'):
            print("   OK: create_agent endpoint exists")
        else:
            print("   ERROR: create_agent NOT found")
            return False
    except Exception as e:
        print(f"   ERROR: {e}")
        return False
    
    # Test 4: Check frontend
    print("\n4. Checking frontend code...")
    try:
        api_js = (Path(project_root) / "static" / "admin" / "js" / "api.js")
        if not api_js.exists():
            print("   ERROR: api.js not found")
            return False
        content = api_js.read_text()
        if "createAgent" in content and "/admin/agents" in content:
            print("   OK: Frontend methods exist")
        else:
            print("   ERROR: Frontend methods missing")
            return False
    except Exception as e:
        print(f"   ERROR: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("CODE IS VALID - Issue is at Runtime")
    print("=" * 60)
    print("\nMost Likely Causes:\n")
    print("1. NO ADMIN USER - Run: python3 scripts/create_admin.py")
    print("2. DATABASE NOT INITIALIZED - Run: python3 scripts/init_db.py")
    print("3. API NOT RUNNING - Run: uvicorn src.main:app --reload")
    print("4. CHECK BROWSER CONSOLE - Press F12, look for errors")
    print("\nTo troubleshoot:")
    print("- Open http://localhost:8000/admin")
    print("- Try to login")
    print("- If login works, try creating agent")
    print("- Check Network tab in DevTools for API errors")

if __name__ == "__main__":
    try:
        check_issue()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
