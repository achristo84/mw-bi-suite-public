"""Add email ingestion support.

Revision ID: 003
Revises: 002
Create Date: 2025-12-13

- Add invoice_email to distributors for matching incoming emails
- Create email_messages table for tracking processed emails
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add invoice_email column to distributors
    # This is the email address invoices arrive FROM for each distributor
    op.add_column(
        'distributors',
        sa.Column('invoice_email', sa.String(255), nullable=True,
                  comment='Email address invoices arrive from (for matching)')
    )

    # Create email_messages table to track processed emails
    op.create_table(
        'email_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('gmail_message_id', sa.String(100), nullable=False, unique=True,
                  comment='Gmail API message ID'),
        sa.Column('gmail_thread_id', sa.String(100),
                  comment='Gmail API thread ID'),
        sa.Column('from_address', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500)),
        sa.Column('received_at', sa.TIMESTAMP, nullable=False,
                  comment='When Gmail received the email'),
        sa.Column('distributor_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('distributors.id'),
                  comment='Matched distributor (null if unknown sender)'),
        sa.Column('status', sa.String(20), nullable=False, default='pending',
                  comment='pending, processing, processed, failed, ignored'),
        sa.Column('has_attachments', sa.Boolean, default=False),
        sa.Column('attachment_count', sa.Integer, default=0),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('invoices.id'),
                  comment='Resulting invoice (if successfully processed)'),
        sa.Column('error_message', sa.Text,
                  comment='Error details if processing failed'),
        sa.Column('processed_at', sa.TIMESTAMP),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.text('NOW()')),
    )

    # Index for finding unprocessed emails
    op.create_index(
        'idx_email_messages_status',
        'email_messages',
        ['status'],
        postgresql_where="status IN ('pending', 'processing')"
    )

    # Index for looking up by Gmail message ID
    op.create_index(
        'idx_email_messages_gmail_id',
        'email_messages',
        ['gmail_message_id']
    )


def downgrade() -> None:
    op.drop_index('idx_email_messages_gmail_id')
    op.drop_index('idx_email_messages_status')
    op.drop_table('email_messages')
    op.drop_column('distributors', 'invoice_email')
