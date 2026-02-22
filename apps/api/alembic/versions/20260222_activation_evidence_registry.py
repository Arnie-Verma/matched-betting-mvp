"""Add canonical activation evidence registry table

Revision ID: 20260222_evidence_registry
Revises: 20260222_lifecycle
Create Date: 2026-02-22 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_evidence_registry"
down_revision: Union[str, Sequence[str], None] = "20260222_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bookmaker_activation_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=20), nullable=False),
        sa.Column("bookmaker_id", sa.Integer(), nullable=False),
        sa.Column("bookmaker_code", sa.String(length=30), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_in_scope_fail_count", sa.Integer(), nullable=True),
        sa.Column("canary_gate_pass", sa.Boolean(), nullable=True),
        sa.Column("canary_gate_thresholds", sa.JSON(), nullable=True),
        sa.Column("canary_gate_failed_criteria", sa.JSON(), nullable=True),
        sa.Column("artifact_path", sa.String(length=500), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("artifact_metadata", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_by_email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["bookmaker_id"], ["bookmakers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bookmaker_code",
            "evidence_type",
            "artifact_sha256",
            name="uq_activation_evidence_code_type_hash",
        ),
    )
    op.create_index("ix_bookmaker_activation_evidence_id", "bookmaker_activation_evidence", ["id"], unique=False)
    op.create_index(
        "idx_activation_evidence_lookup",
        "bookmaker_activation_evidence",
        ["bookmaker_code", "evidence_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_bookmaker_activation_evidence_evidence_type",
        "bookmaker_activation_evidence",
        ["evidence_type"],
        unique=False,
    )
    op.create_index(
        "ix_bookmaker_activation_evidence_bookmaker_id",
        "bookmaker_activation_evidence",
        ["bookmaker_id"],
        unique=False,
    )
    op.create_index(
        "ix_bookmaker_activation_evidence_bookmaker_code",
        "bookmaker_activation_evidence",
        ["bookmaker_code"],
        unique=False,
    )
    op.create_index(
        "ix_bookmaker_activation_evidence_artifact_sha256",
        "bookmaker_activation_evidence",
        ["artifact_sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bookmaker_activation_evidence_artifact_sha256", table_name="bookmaker_activation_evidence")
    op.drop_index("ix_bookmaker_activation_evidence_bookmaker_code", table_name="bookmaker_activation_evidence")
    op.drop_index("ix_bookmaker_activation_evidence_bookmaker_id", table_name="bookmaker_activation_evidence")
    op.drop_index("ix_bookmaker_activation_evidence_evidence_type", table_name="bookmaker_activation_evidence")
    op.drop_index("idx_activation_evidence_lookup", table_name="bookmaker_activation_evidence")
    op.drop_index("ix_bookmaker_activation_evidence_id", table_name="bookmaker_activation_evidence")
    op.drop_table("bookmaker_activation_evidence")
