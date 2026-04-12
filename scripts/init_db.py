#!/usr/bin/env python3
"""
Initialize SatsRemit Database - Direct approach without Alembic CLI
Creates all tables directly from SQLAlchemy ORM models
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def init_database():
    """Initialize database schema from ORM models"""
    try:
        from src.db.database import DatabaseManager
        from src.models.models import Base
        
        print("=" * 60)
        print("SatsRemit Database Initialization")
        print("=" * 60)
        
        # Initialize database manager
        db_manager = DatabaseManager()
        print("✓ Database manager initialized")
        
        # Create all tables
        print("Creating database schema...")
        Base.metadata.create_all(bind=db_manager.engine)
        print("✓ Database schema created successfully")
        
        # Verify tables were created
        inspector_result = db_manager.engine.connect()
        from sqlalchemy import inspect
        inspector = inspect(db_manager.engine)
        tables = inspector.get_table_names()
        
        print(f"\n✓ Created {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  - {table}")
        
        inspector_result.close()
        
        print("\n" + "=" * 60)
        print("Database initialized successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Verify database tables:")
        print("   psql $DATABASE_URL -c \"\\dt\"")
        print("2. Run the API:")
        print("   python -m uvicorn src.main:create_app --reload")
        print("3. Test API:")
        print("   curl http://localhost:8000/health")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error initializing database:")
        print(f"  {e}")
        
        # Print helpful troubleshooting
        print("\nTroubleshooting tips:")
        print("1. Check DATABASE_URL is set:")
        print("   echo $DATABASE_URL")
        print("2. Verify PostgreSQL is running:")
        print("   sudo systemctl status postgresql")
        print("3. Test connection:")
        print("   psql $DATABASE_URL -c 'SELECT 1'")
        print("4. Check .env file exists:")
        print("   cat .env")
        
        return False


def seed_test_data():
    """Seed initial test data (optional)"""
    try:
        from src.db.database import DatabaseManager
        from src.models.models import Agent, AgentStatus
        from src.core.security import hash_password
        from datetime import datetime
        
        db = DatabaseManager()
        session = db.get_session()
        
        print("\nSeeding test data...")
        
        # Create admin user if doesn't exist
        existing_admin = session.query(Agent).filter_by(phone="+263712000000").first()
        if not existing_admin:
            admin = Agent(
                phone="+263712000000",
                name="Admin User",
                location_code="ZWE_ADM",
                location_name="Admin",
                password_hash=hash_password("Admin1234"),
                status=AgentStatus.ACTIVE,
                is_admin=True,
                must_change_password=False,
                cash_balance_zar=0.00,
                commission_balance_sats=0
            )
            session.add(admin)
            session.commit()
            print("✓ Admin user created: +263712000000 (password: Admin1234)")
        else:
            print("✓ Admin user already exists")
        
        # Create test agent if doesn't exist
        existing_agent = session.query(Agent).filter_by(phone="+263784000001").first()
        if not existing_agent:
            agent = Agent(
                phone="+263784000001",
                name="Test Agent Harare",
                location_code="ZWE_HRR",
                location_name="Harare",
                password_hash=hash_password("SecurePassword123!"),
                status=AgentStatus.ACTIVE,
                cash_balance_zar=5000.00,
                commission_balance_sats=0
            )
            session.add(agent)
            session.commit()
            print("✓ Test agent created: +263784000001")
        else:
            print("✓ Test agent already exists")
        
        session.close()
        
    except Exception as e:
        print(f"⚠ Could not seed test data: {e}")


if __name__ == "__main__":
    # Check for .env file
    if not os.path.exists(".env"):
        print("⚠ Warning: .env file not found")
        print("  Copy .env.example to .env and fill in values")
        print("  cp .env.example .env")
        print()
    
    # Initialize database
    success = init_database()
    
    if success:
        # Optionally seed test data
        seed_test_data()
        sys.exit(0)
    else:
        sys.exit(1)
