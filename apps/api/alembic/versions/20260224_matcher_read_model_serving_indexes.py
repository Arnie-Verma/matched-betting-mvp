"""Add matcher read-model serving scalability indexes

Revision ID: 20260224_matcher_rm_idx
Revises: 20260222_matcher_rm
Create Date: 2026-02-24 00:00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260224_matcher_rm_idx"
down_revision: Union[str, Sequence[str], None] = "20260222_matcher_rm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_matcher_rm_version_pnl_id",
        "matcher_read_model_rows",
        ["read_model_version", "pnl_percentage", "id"],
        unique=False,
    )
    op.create_index(
        "idx_matcher_rm_version_bookmaker_pnl_id",
        "matcher_read_model_rows",
        ["read_model_version", "back_bookmaker_code", "pnl_percentage", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_matcher_rm_version_bookmaker_pnl_id", table_name="matcher_read_model_rows")
    op.drop_index("idx_matcher_rm_version_pnl_id", table_name="matcher_read_model_rows")
