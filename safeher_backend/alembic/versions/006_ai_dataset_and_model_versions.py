"""006 ai dataset queue and model versions

Revision ID: 006
Revises: 005
Create Date: 2026-08-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_model_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('model_type', sa.String(32), nullable=False),
        sa.Column('version', sa.String(32), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('artifact_path', sa.Text(), nullable=True),
        sa.Column('metrics', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_ai_model_versions_type_status', 'ai_model_versions', ['model_type', 'status'])

    op.create_table(
        'ai_dataset_samples',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('modality', sa.String(20), nullable=False, server_default='audio'),
        sa.Column('model_version', sa.String(32), nullable=False),
        sa.Column('ai_confidence', sa.Float(), nullable=True),
        sa.Column('user_confirmation', sa.Boolean(), nullable=True),
        sa.Column('label', sa.String(64), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('features', JSONB, nullable=True),
        sa.Column('device_info', JSONB, nullable=True),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='queued'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_ai_dataset_samples_status', 'ai_dataset_samples', ['status'])


def downgrade():
    op.drop_index('ix_ai_dataset_samples_status', table_name='ai_dataset_samples')
    op.drop_table('ai_dataset_samples')
    op.drop_index('ix_ai_model_versions_type_status', table_name='ai_model_versions')
    op.drop_table('ai_model_versions')
