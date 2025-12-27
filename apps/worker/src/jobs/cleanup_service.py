"""
Database cleanup service for production scalability.

Phase 3 Optimization:
- Deletes non-current odds immediately (is_current = false)
- Deletes past events (cascades to markets, selections, odds)
- Keeps database small and queries fast

Design Principles:
- Only delete data that's no longer useful for matched betting
- Never delete future events
- Safe guards against accidental mass deletion
"""
import sys
sys.path.insert(0, "apps/api/src")

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from sqlalchemy import delete, select, func, and_
from sqlalchemy.orm import Session

from api.core.database import SessionLocal
from api.models.odds import OddsSnapshot, Event, Market, Selection

logger = logging.getLogger(__name__)


class CleanupService:
    """Handles database cleanup for production scalability."""

    def __init__(self, db: Session):
        self.db = db

    def cleanup_non_current_odds(self) -> Dict[str, Any]:
        """
        Delete all odds where is_current = false.

        These are old odds that have been superseded by newer scrapes.
        The save_odds.py already marks old odds as is_current=false when
        new odds arrive, so these are safe to delete immediately.

        Returns:
            Dict with deletion count and timing
        """
        start_time = time.time()

        # Count before deletion
        count_before = self.db.scalar(
            select(func.count()).select_from(OddsSnapshot)
        )
        non_current_count = self.db.scalar(
            select(func.count()).select_from(OddsSnapshot).where(
                OddsSnapshot.is_current == False
            )
        )

        logger.info(f"[CLEANUP] Found {non_current_count} non-current odds to delete (total: {count_before})")

        if non_current_count == 0:
            return {
                "deleted": 0,
                "duration_seconds": time.time() - start_time,
                "message": "No non-current odds to delete"
            }

        # Delete non-current odds in batches to avoid long locks
        batch_size = 10000
        total_deleted = 0

        while True:
            # Get IDs of non-current odds (batch)
            batch_ids = self.db.scalars(
                select(OddsSnapshot.id).where(
                    OddsSnapshot.is_current == False
                ).limit(batch_size)
            ).all()

            if not batch_ids:
                break

            # Delete batch
            result = self.db.execute(
                delete(OddsSnapshot).where(
                    OddsSnapshot.id.in_(batch_ids)
                )
            )
            self.db.commit()

            deleted_count = result.rowcount
            total_deleted += deleted_count
            logger.debug(f"[CLEANUP] Deleted batch of {deleted_count} odds")

            if deleted_count < batch_size:
                break

        duration = time.time() - start_time
        logger.info(f"[CLEANUP] Deleted {total_deleted} non-current odds in {duration:.2f}s")

        return {
            "deleted": total_deleted,
            "duration_seconds": duration,
            "message": f"Deleted {total_deleted} non-current odds"
        }

    def cleanup_past_events(self, buffer_hours: int = 2) -> Dict[str, Any]:
        """
        Delete events that have already started (past start_time).

        Manually cascades deletion: odds → selections → markets → events.
        (Database FKs don't have ON DELETE CASCADE, so we handle it in code.)
        Adds a buffer to avoid deleting events that just started (in case of delays).

        Args:
            buffer_hours: Hours after start_time before deletion (default: 2)

        Returns:
            Dict with deletion count and timing
        """
        start_time = time.time()

        # Calculate cutoff time (now - buffer)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=buffer_hours)

        # Count past events
        past_event_count = self.db.scalar(
            select(func.count()).select_from(Event).where(
                Event.start_time < cutoff_time
            )
        )

        logger.info(f"[CLEANUP] Found {past_event_count} past events to delete (start_time < {cutoff_time.isoformat()})")

        if past_event_count == 0:
            return {
                "deleted": 0,
                "duration_seconds": time.time() - start_time,
                "message": "No past events to delete"
            }

        # Safety check: Don't delete more than 1000 events at once
        MAX_DELETE = 1000
        if past_event_count > MAX_DELETE:
            logger.warning(f"[CLEANUP] Limiting deletion to {MAX_DELETE} events (found {past_event_count})")

        # Get event IDs to delete (with limit for safety)
        event_ids = list(self.db.scalars(
            select(Event.id).where(
                Event.start_time < cutoff_time
            ).limit(MAX_DELETE)
        ).all())

        if not event_ids:
            return {
                "deleted": 0,
                "duration_seconds": time.time() - start_time,
                "message": "No past events to delete"
            }

        # Manual cascade: delete from bottom up (odds → selections → markets → events)
        # Step 1: Get market IDs for these events
        market_ids = list(self.db.scalars(
            select(Market.id).where(Market.event_id.in_(event_ids))
        ).all())

        if market_ids:
            # Step 2: Get selection IDs for these markets
            selection_ids = list(self.db.scalars(
                select(Selection.id).where(Selection.market_id.in_(market_ids))
            ).all())

            if selection_ids:
                # Step 3: Delete odds for these selections
                odds_deleted = self.db.execute(
                    delete(OddsSnapshot).where(OddsSnapshot.selection_id.in_(selection_ids))
                ).rowcount
                logger.debug(f"[CLEANUP] Deleted {odds_deleted} odds for past events")

                # Step 4: Delete selections
                selections_deleted = self.db.execute(
                    delete(Selection).where(Selection.id.in_(selection_ids))
                ).rowcount
                logger.debug(f"[CLEANUP] Deleted {selections_deleted} selections for past events")

            # Step 5: Delete markets
            markets_deleted = self.db.execute(
                delete(Market).where(Market.id.in_(market_ids))
            ).rowcount
            logger.debug(f"[CLEANUP] Deleted {markets_deleted} markets for past events")

        # Step 6: Delete events
        events_deleted = self.db.execute(
            delete(Event).where(Event.id.in_(event_ids))
        ).rowcount

        self.db.commit()

        duration = time.time() - start_time

        logger.info(f"[CLEANUP] Deleted {events_deleted} past events (manual cascade: markets, selections, odds) in {duration:.2f}s")

        return {
            "deleted": events_deleted,
            "duration_seconds": duration,
            "message": f"Deleted {events_deleted} past events with manual cascade"
        }

    def cleanup_orphaned_selections(self) -> Dict[str, Any]:
        """
        Delete selections that have no associated odds.

        These can accumulate if scraping creates selections but fails to save odds.

        Returns:
            Dict with deletion count and timing
        """
        start_time = time.time()

        # Find selections with no odds
        orphaned_ids = self.db.scalars(
            select(Selection.id).where(
                ~Selection.id.in_(
                    select(OddsSnapshot.selection_id).distinct()
                )
            ).limit(5000)  # Safety limit
        ).all()

        if not orphaned_ids:
            return {
                "deleted": 0,
                "duration_seconds": time.time() - start_time,
                "message": "No orphaned selections found"
            }

        # Delete orphaned selections
        result = self.db.execute(
            delete(Selection).where(
                Selection.id.in_(orphaned_ids)
            )
        )
        self.db.commit()

        deleted_count = result.rowcount
        duration = time.time() - start_time

        logger.info(f"[CLEANUP] Deleted {deleted_count} orphaned selections in {duration:.2f}s")

        return {
            "deleted": deleted_count,
            "duration_seconds": duration,
            "message": f"Deleted {deleted_count} orphaned selections"
        }

    def cleanup_orphaned_markets(self) -> Dict[str, Any]:
        """
        Delete markets that have no associated selections.

        Returns:
            Dict with deletion count and timing
        """
        start_time = time.time()

        # Find markets with no selections
        orphaned_ids = self.db.scalars(
            select(Market.id).where(
                ~Market.id.in_(
                    select(Selection.market_id).distinct()
                )
            ).limit(5000)  # Safety limit
        ).all()

        if not orphaned_ids:
            return {
                "deleted": 0,
                "duration_seconds": time.time() - start_time,
                "message": "No orphaned markets found"
            }

        # Delete orphaned markets
        result = self.db.execute(
            delete(Market).where(
                Market.id.in_(orphaned_ids)
            )
        )
        self.db.commit()

        deleted_count = result.rowcount
        duration = time.time() - start_time

        logger.info(f"[CLEANUP] Deleted {deleted_count} orphaned markets in {duration:.2f}s")

        return {
            "deleted": deleted_count,
            "duration_seconds": duration,
            "message": f"Deleted {deleted_count} orphaned markets"
        }

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get current database statistics for monitoring.

        Returns:
            Dict with table counts and current/non-current odds breakdown
        """
        stats = {
            "odds_total": self.db.scalar(
                select(func.count()).select_from(OddsSnapshot)
            ),
            "odds_current": self.db.scalar(
                select(func.count()).select_from(OddsSnapshot).where(
                    OddsSnapshot.is_current == True
                )
            ),
            "odds_non_current": self.db.scalar(
                select(func.count()).select_from(OddsSnapshot).where(
                    OddsSnapshot.is_current == False
                )
            ),
            "events_total": self.db.scalar(
                select(func.count()).select_from(Event)
            ),
            "events_upcoming": self.db.scalar(
                select(func.count()).select_from(Event).where(
                    Event.start_time > datetime.now(timezone.utc)
                )
            ),
            "events_past": self.db.scalar(
                select(func.count()).select_from(Event).where(
                    Event.start_time <= datetime.now(timezone.utc)
                )
            ),
            "markets_total": self.db.scalar(
                select(func.count()).select_from(Market)
            ),
            "selections_total": self.db.scalar(
                select(func.count()).select_from(Selection)
            ),
        }

        return stats

    def run_full_cleanup(self) -> Dict[str, Any]:
        """
        Run complete cleanup routine.

        Order matters:
        1. Delete non-current odds (safe, quick)
        2. Delete past events (cascades to markets, selections, remaining odds)
        3. Delete orphaned selections (cleanup stragglers)
        4. Delete orphaned markets (cleanup stragglers)

        Returns:
            Dict with all cleanup results
        """
        start_time = time.time()

        logger.info("[CLEANUP] Starting full database cleanup")

        # Get stats before cleanup
        stats_before = self.get_database_stats()
        logger.info(f"[CLEANUP] Before: {stats_before}")

        # Run cleanup steps
        results = {
            "non_current_odds": self.cleanup_non_current_odds(),
            "past_events": self.cleanup_past_events(),
            "orphaned_selections": self.cleanup_orphaned_selections(),
            "orphaned_markets": self.cleanup_orphaned_markets(),
        }

        # Get stats after cleanup
        stats_after = self.get_database_stats()
        logger.info(f"[CLEANUP] After: {stats_after}")

        total_duration = time.time() - start_time

        # Summary
        total_deleted = sum(r.get("deleted", 0) for r in results.values())

        logger.info(
            f"[CLEANUP] Full cleanup complete in {total_duration:.2f}s. "
            f"Deleted {total_deleted} records total."
        )

        return {
            "success": True,
            "results": results,
            "stats_before": stats_before,
            "stats_after": stats_after,
            "total_deleted": total_deleted,
            "total_duration_seconds": total_duration,
        }


def run_cleanup() -> Dict[str, Any]:
    """
    Convenience function to run full cleanup.

    Can be called from:
    - Scheduled cron job
    - Manual script
    - API endpoint (admin only)

    Returns:
        Dict with cleanup results
    """
    db = SessionLocal()
    try:
        service = CleanupService(db)
        return service.run_full_cleanup()
    finally:
        db.close()


def get_db_stats() -> Dict[str, Any]:
    """
    Get database statistics without performing cleanup.

    Returns:
        Dict with table counts
    """
    db = SessionLocal()
    try:
        service = CleanupService(db)
        return service.get_database_stats()
    finally:
        db.close()


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("Running database cleanup...")
    result = run_cleanup()

    print("\n=== Cleanup Results ===")
    print(f"Total deleted: {result['total_deleted']}")
    print(f"Duration: {result['total_duration_seconds']:.2f}s")
    print("\nBefore:")
    for key, value in result['stats_before'].items():
        print(f"  {key}: {value}")
    print("\nAfter:")
    for key, value in result['stats_after'].items():
        print(f"  {key}: {value}")
