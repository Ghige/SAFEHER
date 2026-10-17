"""007 uniqueness guards for alerts and contacts

Revision ID: 007
Revises: 006
Create Date: 2026-08-30

Stage 2: prevent concurrent duplicate ongoing alerts and duplicate contact phones.
Cleans existing duplicates before creating unique indexes.
"""
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    # Keep newest ongoing alert; cancel older duplicates so unique index can apply.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id
                       ORDER BY started_at DESC NULLS LAST, id DESC
                   ) AS rn
            FROM alerts
            WHERE status IN ('active', 'escalated')
        )
        UPDATE alerts a
        SET status = 'cancelled',
            ended_at = COALESCE(a.ended_at, NOW())
        FROM ranked r
        WHERE a.id = r.id AND r.rn > 1
        """
    )

    # Keep one contact per (user_id, phone_number); delete extras.
    op.execute(
        """
        DELETE FROM emergency_contacts ec
        USING emergency_contacts dup
        WHERE ec.user_id = dup.user_id
          AND ec.phone_number = dup.phone_number
          AND ec.id > dup.id
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_one_ongoing_per_user
        ON alerts (user_id)
        WHERE status IN ('active', 'escalated')
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_emergency_contacts_user_phone
        ON emergency_contacts (user_id, phone_number)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_emergency_contacts_user_phone")
    op.execute("DROP INDEX IF EXISTS uq_alerts_one_ongoing_per_user")
