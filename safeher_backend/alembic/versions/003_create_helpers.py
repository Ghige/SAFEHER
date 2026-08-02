"""003 create helpers

Revision ID: 003
Revises: 002
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'helpers',
        sa.Column('id',                UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('alert_id',          UUID(as_uuid=True), sa.ForeignKey('alerts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('helper_user_id',    UUID(as_uuid=True), sa.ForeignKey('users.id',  ondelete='CASCADE'), nullable=False),
        sa.Column('status',            sa.String(20), default='notified'),
        sa.Column('notified_at',       sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('identity_revealed', sa.Boolean, default=False),
        sa.Column('approved_by_user',  sa.Boolean, default=False),
    )
    op.create_index('ix_helpers_alert_id', 'helpers', ['alert_id'])


def downgrade():
    op.drop_index('ix_helpers_alert_id', table_name='helpers')
    op.drop_table('helpers')
