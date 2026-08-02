"""004 add is_verified to users

Revision ID: 004
Revises: 003
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade():
    op.drop_column('users', 'is_verified')
