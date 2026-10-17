"""008 privacy-safe AI feedback events

Revision ID: 008
Revises: 007
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("ai_dataset_samples")}
    # storage_path was NOT NULL; allow null now that WAV upload is retired.
    if "storage_path" in cols:
        op.alter_column(
            "ai_dataset_samples",
            "storage_path",
            existing_type=sa.Text(),
            nullable=True,
        )
    if "ai_feedback_events" not in inspector.get_table_names():
        op.create_table(
            "ai_feedback_events",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("event_id", sa.String(64), nullable=False),
            sa.Column("session_id", sa.String(64), nullable=False),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("model_version", sa.String(32), nullable=False),
            sa.Column("signal_type", sa.String(20), nullable=False),
            sa.Column("prediction_state", sa.String(32), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("candidate_category", sa.String(48), nullable=False),
            sa.Column("user_feedback", sa.String(32), nullable=False),
            sa.Column("outcome", sa.String(32), nullable=False),
            sa.Column("fp_fn_status", sa.String(48), nullable=False),
            sa.Column("consent_status", sa.String(24), nullable=False),
            sa.Column("consent_version", sa.String(64), nullable=False),
            sa.Column("review_status", sa.String(24), nullable=False, server_default="UNREVIEWED"),
            sa.Column("reviewer_id", sa.String(64), nullable=True),
            sa.Column("license_status", sa.String(32), nullable=False),
            sa.Column("final_verdict", sa.String(24), nullable=True),
            sa.Column("source", sa.String(32), nullable=False, server_default="real_world_app"),
            sa.Column("gold_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("split_bucket", sa.String(16), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("features", JSONB, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("event_id", name="uq_ai_feedback_events_event_id"),
        )
        op.create_index("ix_ai_feedback_events_event_id", "ai_feedback_events", ["event_id"])
        op.create_index("ix_ai_feedback_events_session_id", "ai_feedback_events", ["session_id"])
        op.create_index("ix_ai_feedback_events_user_id", "ai_feedback_events", ["user_id"])
        op.create_index("ix_ai_feedback_events_review_status", "ai_feedback_events", ["review_status"])


def downgrade():
    op.drop_index("ix_ai_feedback_events_review_status", table_name="ai_feedback_events")
    op.drop_index("ix_ai_feedback_events_user_id", table_name="ai_feedback_events")
    op.drop_index("ix_ai_feedback_events_session_id", table_name="ai_feedback_events")
    op.drop_index("ix_ai_feedback_events_event_id", table_name="ai_feedback_events")
    op.drop_table("ai_feedback_events")
    op.alter_column(
        "ai_dataset_samples",
        "storage_path",
        existing_type=sa.Text(),
        nullable=False,
    )
