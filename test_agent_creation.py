"""
Test script to debug agent creation failure
"""
import sys
import json
from datetime import datetime, timedelta
from decimal import Decimal

# Test 1: Check imports
print("=" * 60)
print("TEST 1: Checking imports...")
print("=" * 60)
try:
    from src.api.schemas import AdminAgentCreateRequest, AdminAgentCreateResponse
    print("✅ Schema imports working")
except Exception as e:
    print(f"❌ Schema import failed: {e}")
    sys.exit(1)

try:
    from src.models.models import Agent, AgentStatus
    print("✅ Model imports working")
except Exception as e:
    print(f"❌ Model import failed: {e}")
    sys.exit(1)

try:
    from src.core.security import hash_password, get_current_admin
    print("✅ Security imports working")
except Exception as e:
    print(f"❌ Security import failed: {e}")
    sys.exit(1)

try:
    from src.api.routes import admin
    print("✅ Admin routes import working")
except Exception as e:
    print(f"❌ Admin routes import failed: {e}")
    sys.exit(1)

# Test 2: Validate request schema
print("\n" + "=" * 60)
print("TEST 2: Validating AdminAgentCreateRequest schema...")
print("=" * 60)

test_payload = {
    "phone": "+263712345678",
    "name": "Test Agent",
    "location_code": "harare",
    "initial_cash_zar": 1000.00
}

try:
    request = AdminAgentCreateRequest(**test_payload)
    print(f"✅ Schema validation passed")
    print(f"   Phone: {request.phone}")
    print(f"   Name: {request.name}")
    print(f"   Location Code: {request.location_code}")
    print(f"   Initial Cash: {request.initial_cash_zar} (type: {type(request.initial_cash_zar)})")
except Exception as e:
    print(f"❌ Schema validation failed: {e}")
    print(f"   Payload: {test_payload}")
    sys.exit(1)

# Test 3: Check hash_password function
print("\n" + "=" * 60)
print("TEST 3: Testing password hashing...")
print("=" * 60)

try:
    hashed =hash_password("TempPassword123!")
    print(f"✅ Password hashing working")
    print(f"   Hashed: {hashed[:20]}..." if len(hashed) > 20 else f"   Hashed: {hashed}")
except Exception as e:
    print(f"❌ Password hashing failed: {e}")
    sys.exit(1)

# Test 4: Check Agent model instantiation
print("\n" + "=" * 60)
print("TEST 4: Testing Agent model instantiation...")
print("=" * 60)

try:
    import uuid
    agent = Agent(
        id=uuid.uuid4(),
        phone="+263712345678",
        name="Test Agent",
        email=None,
        password_hash=hash_password("TempPassword123!"),
        location_code="harare",
        location_name="harare",
        cash_balance_zar=Decimal("1000.00"),
        commission_balance_sats=0,
        status=AgentStatus.ACTIVE,
        is_admin=False,
        must_change_password=True,
        rating=None,
        total_transfers=0,
    )
    print(f"✅ Agent model instantiation working")
    print(f"   Agent ID: {agent.id}")
    print(f"   Phone: {agent.phone}")
    print(f"   Cash Balance: {agent.cash_balance_zar}")
except Exception as e:
    print(f"❌ Agent model instantiation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Check response schema
print("\n" + "=" * 60)
print("TEST 5: Validating AdminAgentCreateResponse schema...")
print("=" * 60)

try:
    response = AdminAgentCreateResponse(
        agent_id=str(agent.id),
        phone=agent.phone,
        name=agent.name,
        status=agent.status.value,
        cash_balance_zar=agent.cash_balance_zar,
    )
    print(f"✅ Response schema validation passed")
    print(f"   Agent ID: {response.agent_id}")
    print(f"   Phone: {response.phone}")
    print(f"   Status: {response.status}")
except Exception as e:
    print(f"❌ Response schema validation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Check endpoint existence
print("\n" + "=" * 60)
print("TEST 6: Checking endpoint registration...")
print("=" * 60)

try:
    from src.main import app
    # Get all routes
    routes = app.routes
    admin_agents_post_found = False
    
    for route in routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            if '/api/admin/agents' in route.path and 'POST' in route.methods:
                admin_agents_post_found = True
                print(f"✅ POST /api/admin/agents endpoint found")
                
    if not admin_agents_post_found:
        print(f"❌ POST /api/admin/agents endpoint NOT found")
        print(f"\n   Available routes:")
        for route in routes:
            if hasattr(route, 'path'):
                methods = getattr(route, 'methods', [])
                if '/admin' in route.path:
                    print(f"      {methods} {route.path}")
except Exception as e:
    print(f"❌ Could not check endpoint: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("ALL TESTS COMPLETED")
print("=" * 60)
