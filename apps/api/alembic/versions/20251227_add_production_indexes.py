"""Add production-optimized indexes for 1000+ users scale

Revision ID: 20251227_prod_indexes
Revises: 20251226_idempotent
Create Date: 2025-12-27 00:00:00

Phase 3 Database Optimization:
- Partial indexes for hot-path queries (is_current = true)
- Covering index for odds matcher queries
- Cleanup index for past events
- These indexes keep the working set small and queries fast
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251227_prod_indexes'
down_revision: Union[str, Sequence[str], None] = '20251226_idempotent'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add production-optimized indexes for scale.

    New indexes:
    1. Partial index on current odds only (90%+ smaller than full index)
    2. Covering index for matcher queries (avoids table lookup)
    3. Partial index on upcoming events (for matcher queries)
    4. Index for cleanup queries on past events

    Note: Using regular CREATE INDEX (not CONCURRENTLY) since Alembic runs in a transaction.
    For production with large tables, run these manually with CONCURRENTLY outside of migration.
    """

    # 1. Partial index on current odds - CRITICAL for matcher performance
    # Most queries filter on is_current = true, so only index those rows
    # This makes the index ~90% smaller and much faster to scan
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_current_only
        ON odds_snapshots (selection_id, bookmaker_id)
        WHERE is_current = true
    """)

    # 2. Covering index for matcher - includes odds value to avoid table lookup
    # The matcher needs: selection_id, bookmaker_id, decimal_odds, available_amount
    # By including these in the index, we avoid hitting the table for each row
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_odds_matcher_covering
        ON odds_snapshots (selection_id, bookmaker_id, decimal_odds, available_amount)
        WHERE is_current = true
    """)

    # 3. Partial index on upcoming events for matcher queries
    # Matcher only queries events with start_time > now(), so index only those
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_upcoming
        ON events (competition_id, start_time)
        WHERE status = 'scheduled'
    """)

    # 4. Index for cleanup - find past events efficiently
    # Used by cleanup_past_events() to quickly find deletable events
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_past_cleanup
        ON events (start_time)
    """)

    # 5. Index for bookmaker code lookup (used in every matcher query)
    # This speeds up the JOIN between odds_snapshots and bookmakers
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bookmaker_code_active
        ON bookmakers (code)
        WHERE is_active = true
    """)


def downgrade() -> None:
    """
    Remove production indexes.
    """
    op.execute("DROP INDEX IF EXISTS idx_odds_current_only")
    op.execute("DROP INDEX IF EXISTS idx_odds_matcher_covering")
    op.execute("DROP INDEX IF EXISTS idx_events_upcoming")
    op.execute("DROP INDEX IF EXISTS idx_events_past_cleanup")
    op.execute("DROP INDEX IF EXISTS idx_bookmaker_code_active")
