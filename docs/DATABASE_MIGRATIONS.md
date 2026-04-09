# Database Migrations Guide

## Overview

SatsRemit uses **Alembic** for database migration management. This guide explains how to set up the database, run migrations, and manage schema changes.

## Directory Structure

```
alembic/
├── versions/              # Migration scripts
│   ├── __init__.py
│   └── 001_initial_schema.py    # Initial migration (creates all tables)
├── env.py                 # Migration environment setup
├── script.py.mako         # Template for new migrations
alembic.ini               # Alembic configuration
scripts/migrate.py        # Migration runner script
```

## Quick Start

### 1. Prerequisites

Ensure you have the required packages:
```bash
pip install -r requirements.txt
```

Required packages: `alembic`, `sqlalchemy`, `psycopg2-binary`

### 2. Configure Database URL

Update your `.env` file with the PostgreSQL connection string:

```bash
# .env
DATABASE_URL=postgresql://satsremit:password@localhost:5432/satsremit
```

Or export it:
```bash
export DATABASE_URL="postgresql://satsremit:password@localhost:5432/satsremit"
```

### 3. Run Initial Migration

Apply all migrations up to the head:

```bash
python scripts/migrate.py upgrade head
```

This will:
- Create all ENUM types (TransferState, AgentStatus, SettlementStatus)
- Create 8 tables: agents, transfers, settlements, invoice_holds, transfer_history, rate_cache, webhooks
- Create all indices for performance
- Create foreign key relationships

### 4. Verify Migration

Check current revision:
```bash
python scripts/migrate.py current
```

View migration history:
```bash
python scripts/migrate.py history
```

### 5. Test Database Connection

```bash
python -c "
from src.db.database import DatabaseManager
db = DatabaseManager()
db.create_tables()
print('✓ Database connected and tables verified')
"
```

## Migration Commands

### Upgrade to specific revision
```bash
python scripts/migrate.py upgrade 001_initial_schema
```

### Upgrade to latest (head)
```bash
python scripts/migrate.py upgrade head
```

### Downgrade by 1 step
```bash
python scripts/migrate.py downgrade -1
```

### Downgrade to specific revision
```bash
python scripts/migrate.py downgrade 001_initial_schema
```

### Check current revision
```bash
python scripts/migrate.py current
```

### View all migrations
```bash
python scripts/migrate.py history
```

## Database Schema

### Tables Created

#### 1. **agents** - Cash payout operators
- `id` (UUID, PK)
- `phone` (String, unique)
- `name` (String)
- `password_hash` (String)
- `location_code` (String)
- `location_name` (String)
- `cash_balance_zar` (Decimal)
- `commission_balance_sats` (Integer)
- `status` (ENUM: ACTIVE, INACTIVE, SUSPENDED)
- `rating` (Float)
- `total_transfers` (Integer)
- `created_at`, `updated_at`, `last_login_at` (DateTime)

**Indices**: phone (unique), email, status

#### 2. **transfers** - Remittance transactions
- `id` (UUID, PK)
- `reference` (String, unique) - Human-friendly reference
- `sender_phone`, `receiver_phone`, `receiver_name` (String)
- `receiver_location` (String)
- `agent_id` (UUID, FK → agents)
- `amount_zar`, `amount_sats` (Decimal/Integer)
- `rate_zar_per_btc` (Decimal) - Rate locked at transaction time
- `invoice_hash` (String, unique) - LND invoice hash
- `payment_request` (String) - BOLT11 invoice string
- `state` (ENUM: 8 states from INITIATED to REFUNDED)
- `receiver_phone_verified`, `agent_verified` (Boolean)
- `verified_at`, `payout_at`, `settled_at` (DateTime)
- `pin_generated` (String) - Hashed PIN
- `notes` (String)
- `created_at`, `updated_at` (DateTime)

**Indices**: reference, sender_phone, receiver_phone, agent_id, invoice_hash, state, created_at

#### 3. **settlements** - Weekly agent payouts
- `id` (UUID, PK)
- `agent_id` (UUID, FK → agents)
- `period_start`, `period_end` (DateTime)
- `amount_zar_owed`, `amount_zar_paid` (Decimal)
- `commission_sats_earned` (Integer)
- `payment_method` (String)
- `payment_reference` (String)
- `status` (ENUM: PENDING, CONFIRMED, COMPLETED)
- `confirmed_at`, `completed_at` (DateTime)
- `created_at`, `updated_at` (DateTime)

**Indices**: agent_id

#### 4. **invoice_holds** - HTLC secret management
- `id` (UUID, PK)
- `invoice_hash` (String, unique) - LND invoice hash
- `transfer_id` (UUID, FK → transfers, unique)
- `preimage` (String) - Encrypted preimage
- `expires_at` (DateTime)
- `created_at` (DateTime)

**Indices**: invoice_hash

#### 5. **transfer_history** - Audit trail
- `id` (UUID, PK)
- `transfer_id` (UUID, FK → transfers)
- `old_state`, `new_state` (ENUM)
- `reason` (String)
- `actor_type` (String: "system", "sender", "agent", "admin")
- `actor_id` (String)
- `created_at` (DateTime)

**Indices**: transfer_id, created_at

#### 6. **rate_cache** - Exchange rates
- `id` (UUID, PK)
- `pair` (String, unique) - e.g., "ZAR_BTC"
- `rate` (Decimal)
- `source` (String) - "coingecko", "kraken", etc.
- `cached_at`, `updated_at` (DateTime)

**Indices**: pair (unique)

#### 7. **webhooks** - Event delivery tracking
- `id` (UUID, PK)
- `event_type` (String) - e.g., "lnd.invoice.settled"
- `payload` (JSON)
- `status` (String: "pending", "delivered", "failed")
- `retry_count` (Integer)
- `error_message` (String)
- `created_at`, `processed_at` (DateTime)

**Indices**: event_type, created_at

## Creating New Migrations

When you modify ORM models, create a new migration:

```bash
# Generate migration based on model changes
python scripts/migrate.py generate "add_new_column_to_transfers"
```

Then edit the migration file in `alembic/versions/`:

```python
def upgrade():
    op.add_column('transfers', sa.Column('new_column', sa.String(100), nullable=True))

def downgrade():
    op.drop_column('transfers', 'new_column')
```

Apply it:
```bash
python scripts/migrate.py upgrade head
```

## Common Tasks

### Reset Database (Development Only)

```bash
# Drop all tables and ENUM types
python scripts/migrate.py downgrade base

# Recreate schema
python scripts/migrate.py upgrade head
```

### Seed Test Data

```bash
# See scripts/seed_data.py
python scripts/seed_data.py
```

### Backup Database

```bash
# PostgreSQL backup
pg_dump postgresql://satsremit:password@localhost:5432/satsremit > backup.sql

# With compression
pg_dump postgresql://satsremit:password@localhost:5432/satsremit | gzip > backup.sql.gz
```

### Restore Database

```bash
# From backup
psql postgresql://satsremit:password@localhost:5432/satsremit < backup.sql

# From compressed backup
zcat backup.sql.gz | psql postgresql://satsremit:password@localhost:5432/satsremit
```

## Troubleshooting

### "sqlalchemy.exc.ProgrammingError: relation does not exist"

**Cause**: Migration hasn't been run  
**Solution**: Run `python scripts/migrate.py upgrade head`

### "alembic.util.exc.CommandError: Can't locate revision identified by"

**Cause**: Invalid revision identifier  
**Solution**: Check migration files in `alembic/versions/` and use correct revision ID

### "psycopg2.OperationalError: could not connect to server"

**Cause**: PostgreSQL not running or wrong connection string  
**Solution**: 
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Verify DATABASE_URL: `echo $DATABASE_URL`
- Test connection: `psql $DATABASE_URL`

### "ERROR: type "transferstate" already exists"

**Cause**: Downgrade then upgrade re-created ENUMs  
**Solution**: Use downgrade base, then upgrade head to fresh state

## Integration with FastAPI

SatsRemit initializes the database on startup:

```python
# In src/main.py
from src.db.database import DatabaseManager

db_manager = DatabaseManager()
db_manager.create_tables()  # Called on app startup
```

This ensures tables exist before first request.

## Environment Variables

```bash
# Database configuration
DATABASE_URL=postgresql://user:password@host:5432/dbname
DATABASE_ECHO=False  # Set to True to log all SQL queries

# Migration settings
MIGRATION_ENV=development  # or production
```

## Best Practices

1. **Always backup before migrations**: `pg_dump ... > backup.sql`
2. **Test migrations locally first**: Run on dev database
3. **Keep migrations small**: One logical change per migration
4. **Document migrations**: Add migration reason in docstrings
5. **Review schema changes**: Understand what each migration does
6. **Monitor migration performance**: Large tables may need CONCURRENT operations

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/orm/)
- [PostgreSQL Operations](https://www.postgresql.org/docs/)

---

**Migration Status**: ✅ Initial migration complete (001_initial_schema)  
**Last Updated**: April 9, 2026  
**Next Steps**: Run `python scripts/migrate.py upgrade head` to initialize database
