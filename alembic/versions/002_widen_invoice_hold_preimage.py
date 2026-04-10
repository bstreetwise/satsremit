"""Widen invoice_holds.preimage from VARCHAR(128) to VARCHAR(512)

Revision ID: 002_widen_invoice_hold_preimage
Revises: 001_initial_schema
Create Date: 2026-04-10

Background
----------
The original schema defined ``invoice_holds.preimage`` as ``VARCHAR(128)``.
A Fernet ciphertext for a 64-character hex plaintext is approximately
180 characters (128-bit AES CBC + PKCS7 padding + 32-byte HMAC + base64
overhead).  Any preimage stored after this column was added would have been
silently truncated to 128 characters, making ``decrypt_preimage()`` raise
``InvalidToken`` on every subsequent read — effectively bricking all payout
recovery paths.

This migration widens the column to ``VARCHAR(512)``, which gives safe
headroom for the current Fernet output (~180 chars) and any future
algorithm changes.

The column is also now managed by the ``EncryptedPreimage`` SQLAlchemy
``TypeDecorator`` (``src/core/security.py``) which transparently encrypts
on write and decrypts on read, so application code never handles raw
ciphertext.

Existing rows
-------------
Any rows created with the old schema will have truncated ciphertexts that
cannot be decrypted.  The post-migration step below detects and logs them
so they can be investigated.  Affected transfers should be manually reviewed
— they may need to be refunded if the preimage cannot be recovered.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "002_widen_invoice_hold_preimage"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen the preimage column.
    # PostgreSQL ALTER COLUMN … TYPE is safe on an empty or small table and
    # does not require a table rewrite for VARCHAR widening.
    op.alter_column(
        "invoice_holds",
        "preimage",
        existing_type=sa.String(128),
        type_=sa.String(512),
        existing_nullable=False,
    )

    # Detect rows whose preimage was likely truncated (ciphertext shorter
    # than the minimum valid Fernet token length of ~144 chars).
    # Log them as warnings so operators can investigate.
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            "SELECT id, invoice_hash, transfer_id, length(preimage) AS preimage_len "
            "FROM invoice_holds "
            "WHERE length(preimage) < 144"
        )
    )
    rows = result.fetchall()
    if rows:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Migration 002: found {len(rows)} invoice_holds row(s) with a "
            "preimage shorter than 144 characters — these were likely truncated "
            "by the VARCHAR(128) constraint and cannot be decrypted. "
            "Affected transfer IDs: %s",
            [str(r.transfer_id) for r in rows],
        )


def downgrade() -> None:
    # Narrowing back to VARCHAR(128) will silently truncate any ciphertexts
    # longer than 128 chars.  Warn explicitly.
    import logging
    logging.getLogger(__name__).warning(
        "Downgrading invoice_holds.preimage to VARCHAR(128) will truncate "
        "all existing Fernet ciphertexts.  Do not downgrade on a live system."
    )
    op.alter_column(
        "invoice_holds",
        "preimage",
        existing_type=sa.String(512),
        type_=sa.String(128),
        existing_nullable=False,
    )
