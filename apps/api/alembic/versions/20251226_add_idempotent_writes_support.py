"""Add idempotent writes support - timestamp_bucket and dedupe constraint

Revision ID: 20251226_idempotent
Revises: 26fde4226a2f
Create Date: 2025-12-26 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251226_idempotent'
down_revision: Union[str, Sequence[str], None] = '26fde4226a2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add timestamp_bucket column and new dedupe constraint to odds_snapshots.

    Changes:
    1. Add timestamp_bucket column (nullable for existing rows)
    2. Add index on timestamp_bucket for cleanup queries
    3. Drop old unique constraint uq_odds_selection_bookmaker_time
    4. Add new unique constraint uq_odds_dedupe on (selection_id, bookmaker_id, timestamp_bucket, scrape_session_id)
    """
    # Add timestamp_bucket column (nullable to allow existing rows)
    op.add_column('odds_snapshots',
                  sa.Column('timestamp_bucket', sa.DateTime(timezone=True), nullable=True))

    # Add index on timestamp_bucket for cleanup queries
    op.create_index('idx_odds_timestamp_bucket', 'odds_snapshots', ['timestamp_bucket'], unique=False)

    # Drop old unique constraint
    # Note: Constraint name might vary - check your database if this fails
    try:
        op.drop_constraint('uq_odds_selection_bookmaker_time', 'odds_snapshots', type_='unique')
    except Exception as e:
        # Constraint might not exist or have different name
        print(f"Warning: Could not drop old constraint: {e}")

    # Add new dedupe constraint
    # This allows same odds at same timestamp_bucket from different scrape sessions
    # But prevents duplicate odds from same scrape session at same timestamp_bucket
    op.create_unique_constraint(
        'uq_odds_dedupe',
        'odds_snapshots',
        ['selection_id', 'bookmaker_id', 'timestamp_bucket', 'scrape_session_id']
    )


def downgrade() -> None:
    """
    Revert changes - remove timestamp_bucket and restore old constraint.
    """
    # Drop new constraint
    op.drop_constraint('uq_odds_dedupe', 'odds_snapshots', type_='unique')

    # Restore old constraint
    op.create_unique_constraint(
        'uq_odds_selection_bookmaker_time',
        'odds_snapshots',
        ['selection_id', 'bookmaker_id', 'timestamp']
    )

    # Drop index
    op.drop_index('idx_odds_timestamp_bucket', table_name='odds_snapshots')

    # Drop column
    op.drop_column('odds_snapshots', 'timestamp_bucket')
