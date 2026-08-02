"""001 create users

Revision ID: 001
Revises: 
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id',              UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('phone_number',    sa.String(15),  nullable=False, unique=True),
        sa.Column('name',            sa.String(100), nullable=False),
        sa.Column('city',            sa.String(50),  nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('drive_token',     sa.Text,        nullable=True),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_active',     sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_users_phone_number', 'users', ['phone_number'], unique=True)

    op.create_table(
        'emergency_contacts',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',      UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name',         sa.String(100), nullable=False),
        sa.Column('phone_number', sa.String(15),  nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=True),
        sa.Column('ring_priority',sa.Integer,     default=1),
        sa.Column('is_active',    sa.Boolean,     default=True),
    )

    op.create_table(
        'blocklist',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',       UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('blocked_phone', sa.String(15), nullable=False),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('blocklist')
    op.drop_table('emergency_contacts')
    op.drop_index('ix_users_phone_number', table_name='users')
    op.drop_table('users')
