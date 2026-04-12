#!/usr/bin/env python3
"""
Create Admin User - Standalone script to add admin to existing database
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def create_admin(phone, password, name="Admin User"):
    """Create admin user in database"""
    try:
        from src.db.database import DatabaseManager
        from src.models.models import Agent, AgentStatus
        from src.core.security import hash_password
        
        db = DatabaseManager()
        session = db.get_session()
        
        print("=" * 60)
        print("SatsRemit - Create Admin User")
        print("=" * 60)
        
        # Check if admin already exists
        existing = session.query(Agent).filter_by(phone=phone).first()
        if existing:
            if existing.is_admin:
                print(f"\n✓ Admin user already exists: {phone}")
                print(f"  Name: {existing.name}")
                print(f"  Status: {existing.status.value}")
            else:
                print(f"\n⚠ Non-admin agent exists with this phone: {phone}")
                print(f"  Upgrade to admin? (y/n)")
                response = input("> ").lower().strip()
                if response == 'y':
                    existing.is_admin = True
                    existing.must_change_password = False
                    session.commit()
                    print(f"✓ Agent {phone} upgraded to admin!")
                else:
                    print("✗ Cancelled")
            session.close()
            return True
        
        # Create new admin
        admin = Agent(
            phone=phone,
            name=name,
            location_code="ZWE_ADM",
            location_name="Admin",
            password_hash=hash_password(password),
            status=AgentStatus.ACTIVE,
            is_admin=True,
            must_change_password=False,
            cash_balance_zar=0.00,
            commission_balance_sats=0
        )
        
        session.add(admin)
        session.commit()
        
        print(f"\n✓ Admin user created successfully!")
        print(f"  Phone: {phone}")
        print(f"  Password: {password}")
        print(f"  Name: {name}")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Error creating admin user:")
        print(f"  {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Check for .env file
    if not os.path.exists(".env"):
        print("⚠ Warning: .env file not found")
        print("  Copy .env.example to .env and fill in values")
        print("  cp .env.example .env")
        sys.exit(1)
    
    # Get phone and password
    if len(sys.argv) > 2:
        phone = sys.argv[1]
        password = sys.argv[2]
        name = sys.argv[3] if len(sys.argv) > 3 else "Admin User"
    else:
        print("Interactive Admin Creation")
        print("-" * 60)
        phone = input("Enter admin phone number (+263...): ").strip()
        if not phone:
            print("✗ Phone number required")
            sys.exit(1)
        
        password = input("Enter admin password: ").strip()
        if not password or len(password) < 8:
            print("✗ Password must be at least 8 characters")
            sys.exit(1)
        
        name = input("Enter admin name (default: Admin User): ").strip()
        if not name:
            name = "Admin User"
    
    # Create admin
    success = create_admin(phone, password, name)
    sys.exit(0 if success else 1)
