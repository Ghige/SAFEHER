"""002 create alerts

Revision ID: 002
Revises: 001
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'alerts',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',      UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trigger_type', sa.String(20),  nullable=False),
        sa.Column('latitude',     sa.DECIMAL(10, 8), nullable=True),
        sa.Column('longitude',    sa.DECIMAL(11, 8), nullable=True),
        sa.Column('status',       sa.String(20),  default='active'),
        sa.Column('started_at',   sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('ended_at',     sa.DateTime(timezone=True), nullable=True),
        sa.Column('evidence_url', sa.Text, nullable=True),
    )
    op.create_index('ix_alerts_user_id', 'alerts', ['user_id'])
    op.create_index('ix_alerts_status',  'alerts', ['status'])


def downgrade():
    op.drop_index('ix_alerts_status',  table_name='alerts')
    op.drop_index('ix_alerts_user_id', table_name='alerts')
    op.drop_table('alerts')
