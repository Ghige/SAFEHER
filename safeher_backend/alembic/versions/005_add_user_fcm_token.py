"""005 add fcm_token to users

Revision ID: 005
Revises: 004
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('fcm_token', sa.String(512), nullable=True))


def downgrade():
    op.drop_column('users', 'fcm_token')
