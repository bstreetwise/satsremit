"""Initial database schema - Create all tables

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-04-09 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial database schema with all tables"""
    
    # Create ENUM types
    op.execute("CREATE TYPE transferstate AS ENUM ('INITIATED', 'INVOICE_GENERATED', 'PAYMENT_LOCKED', 'RECEIVER_VERIFIED', 'PAYOUT_EXECUTED', 'SETTLED', 'FINAL', 'REFUNDED')")
    op.execute("CREATE TYPE agentstatus AS ENUM ('ACTIVE', 'INACTIVE', 'SUSPENDED')")
    op.execute("CREATE TYPE settlementstatus AS ENUM ('PENDING', 'CONFIRMED', 'COMPLETED')")
    
    # agents table
    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(120), nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('location_code', sa.String(10), nullable=False),
        sa.Column('location_name', sa.String(100), nullable=False),
        sa.Column('cash_balance_zar', sa.DECIMAL(15, 2), nullable=False, server_default='0'),
        sa.Column('commission_balance_sats', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.Enum('ACTIVE', 'INACTIVE', 'SUSPENDED', name='agentstatus'), nullable=False, server_default='ACTIVE'),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('total_transfers', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_agents_phone'), 'agents', ['phone'], unique=True)
    op.create_index(op.f('ix_agents_email'), 'agents', ['email'], unique=False)
    
    # transfers table
    op.create_table(
        'transfers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reference', sa.String(20), nullable=False),
        sa.Column('sender_phone', sa.String(20), nullable=False),
        sa.Column('receiver_phone', sa.String(20), nullable=False),
        sa.Column('receiver_name', sa.String(100), nullable=False),
        sa.Column('receiver_location', sa.String(50), nullable=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount_zar', sa.DECIMAL(15, 2), nullable=False),
        sa.Column('amount_sats', sa.Integer(), nullable=False),
        sa.Column('rate_zar_per_btc', sa.DECIMAL(15, 2), nullable=False),
        sa.Column('invoice_hash', sa.String(66), nullable=True),
        sa.Column('payment_request', sa.String(2048), nullable=True),
        sa.Column('invoice_expiry_at', sa.DateTime(), nullable=True),
        sa.Column('state', sa.Enum('INITIATED', 'INVOICE_GENERATED', 'PAYMENT_LOCKED', 'RECEIVER_VERIFIED', 'PAYOUT_EXECUTED', 'SETTLED', 'FINAL', 'REFUNDED', name='transferstate'), nullable=False, server_default='INITIATED'),
        sa.Column('receiver_phone_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('agent_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('payout_at', sa.DateTime(), nullable=True),
        sa.Column('settled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('pin_generated', sa.String(4), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference'),
        sa.UniqueConstraint('invoice_hash')
    )
    op.create_index(op.f('ix_transfers_reference'), 'transfers', ['reference'], unique=True)
    op.create_index(op.f('ix_transfers_sender_phone'), 'transfers', ['sender_phone'], unique=False)
    op.create_index(op.f('ix_transfers_receiver_phone'), 'transfers', ['receiver_phone'], unique=False)
    op.create_index(op.f('ix_transfers_agent_id'), 'transfers', ['agent_id'], unique=False)
    op.create_index(op.f('ix_transfers_invoice_hash'), 'transfers', ['invoice_hash'], unique=True)
    op.create_index(op.f('ix_transfers_state'), 'transfers', ['state'], unique=False)
    op.create_index(op.f('ix_transfers_created_at'), 'transfers', ['created_at'], unique=False)
    
    # settlements table
    op.create_table(
        'settlements',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('amount_zar_owed', sa.DECIMAL(15, 2), nullable=False),
        sa.Column('amount_zar_paid', sa.DECIMAL(15, 2), nullable=False, server_default='0'),
        sa.Column('commission_sats_earned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('payment_reference', sa.String(100), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'CONFIRMED', 'COMPLETED', name='settlementstatus'), nullable=False, server_default='PENDING'),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settlements_agent_id'), 'settlements', ['agent_id'], unique=False)
    
    # invoice_holds table (for HTLC secrets)
    op.create_table(
        'invoice_holds',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_hash', sa.String(66), nullable=False),
        sa.Column('transfer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('preimage', sa.String(128), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['transfer_id'], ['transfers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_hash'),
        sa.UniqueConstraint('transfer_id')
    )
    op.create_index(op.f('ix_invoice_holds_invoice_hash'), 'invoice_holds', ['invoice_hash'], unique=True)
    
    # transfer_history table (audit log)
    op.create_table(
        'transfer_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transfer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_state', sa.Enum('INITIATED', 'INVOICE_GENERATED', 'PAYMENT_LOCKED', 'RECEIVER_VERIFIED', 'PAYOUT_EXECUTED', 'SETTLED', 'FINAL', 'REFUNDED', name='transferstate'), nullable=True),
        sa.Column('new_state', sa.Enum('INITIATED', 'INVOICE_GENERATED', 'PAYMENT_LOCKED', 'RECEIVER_VERIFIED', 'PAYOUT_EXECUTED', 'SETTLED', 'FINAL', 'REFUNDED', name='transferstate'), nullable=False),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column('actor_type', sa.String(20), nullable=False),
        sa.Column('actor_id', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['transfer_id'], ['transfers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transfer_history_transfer_id'), 'transfer_history', ['transfer_id'], unique=False)
    op.create_index(op.f('ix_transfer_history_created_at'), 'transfer_history', ['created_at'], unique=False)
    
    # rate_cache table
    op.create_table(
        'rate_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pair', sa.String(10), nullable=False),
        sa.Column('rate', sa.DECIMAL(20, 8), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('cached_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pair')
    )
    op.create_index(op.f('ix_rate_cache_pair'), 'rate_cache', ['pair'], unique=True)
    
    # webhooks table (for delivery tracking)
    op.create_table(
        'webhooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_webhooks_event_type'), 'webhooks', ['event_type'], unique=False)
    op.create_index(op.f('ix_webhooks_created_at'), 'webhooks', ['created_at'], unique=False)


def downgrade() -> None:
    """Drop all tables and enums"""
    
    # Drop tables in reverse order
    op.drop_index(op.f('ix_webhooks_created_at'), table_name='webhooks')
    op.drop_index(op.f('ix_webhooks_event_type'), table_name='webhooks')
    op.drop_table('webhooks')
    
    op.drop_index(op.f('ix_rate_cache_pair'), table_name='rate_cache')
    op.drop_table('rate_cache')
    
    op.drop_index(op.f('ix_transfer_history_created_at'), table_name='transfer_history')
    op.drop_index(op.f('ix_transfer_history_transfer_id'), table_name='transfer_history')
    op.drop_table('transfer_history')
    
    op.drop_index(op.f('ix_invoice_holds_invoice_hash'), table_name='invoice_holds')
    op.drop_table('invoice_holds')
    
    op.drop_index(op.f('ix_settlements_agent_id'), table_name='settlements')
    op.drop_table('settlements')
    
    op.drop_index(op.f('ix_transfers_created_at'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_state'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_invoice_hash'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_agent_id'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_receiver_phone'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_sender_phone'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_reference'), table_name='transfers')
    op.drop_table('transfers')
    
    op.drop_index(op.f('ix_agents_email'), table_name='agents')
    op.drop_index(op.f('ix_agents_phone'), table_name='agents')
    op.drop_table('agents')
    
    # Drop ENUM types
    op.execute("DROP TYPE settlementstatus")
    op.execute("DROP TYPE agentstatus")
    op.execute("DROP TYPE transferstate")
