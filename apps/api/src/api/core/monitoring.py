"""
Monitoring and error tracking configuration.

Uses Sentry for error tracking and performance monitoring.
Free tier provides 5K errors/month which is sufficient for early production.

Setup:
1. Create account at sentry.io
2. Create new project (Python/FastAPI)
3. Copy DSN to environment variable SENTRY_DSN
4. Call init_sentry() in app startup

Usage:
    from api.core.monitoring import init_sentry, capture_exception, capture_message

    # In main.py startup
    init_sentry()

    # In code
    try:
        scrape_bookmaker()
    except Exception as e:
        capture_exception(e, {"bookmaker": "ladbrokes", "sport": "soccer"})
"""
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Sentry SDK is optional - gracefully handle if not installed
try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    logger.warning("sentry-sdk not installed. Error tracking disabled.")


def init_sentry(
    dsn: Optional[str] = None,
    environment: Optional[str] = None,
    release: Optional[str] = None,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
) -> bool:
    """
    Initialize Sentry error tracking.

    Args:
        dsn: Sentry DSN (defaults to SENTRY_DSN env var)
        environment: Environment name (defaults to ENVIRONMENT env var or 'development')
        release: Release version (defaults to APP_VERSION env var)
        traces_sample_rate: Performance tracing sample rate (0.0 to 1.0)
        profiles_sample_rate: Profiling sample rate (0.0 to 1.0)

    Returns:
        True if Sentry was initialized, False otherwise
    """
    if not SENTRY_AVAILABLE:
        logger.warning("Sentry SDK not available. Skipping initialization.")
        return False

    dsn = dsn or os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("SENTRY_DSN not set. Error tracking disabled.")
        return False

    environment = environment or os.getenv("ENVIRONMENT", "development")
    release = release or os.getenv("APP_VERSION", "unknown")

    # Configure logging integration to capture errors from logger.error()
    logging_integration = LoggingIntegration(
        level=logging.INFO,        # Capture info and above as breadcrumbs
        event_level=logging.ERROR  # Send errors to Sentry
    )

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            integrations=[logging_integration],
            # Performance settings for production
            send_default_pii=False,  # Don't send user PII
            attach_stacktrace=True,  # Always attach stack traces
            # Scrubbing sensitive data
            before_send=_before_send,
        )
        logger.info(f"Sentry initialized: environment={environment}, release={release}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False


def _before_send(event: Dict, hint: Dict) -> Optional[Dict]:
    """
    Process events before sending to Sentry.

    Used for:
    - Filtering out non-actionable errors
    - Scrubbing sensitive data
    - Adding custom context
    """
    # Filter out common non-actionable errors
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]

        # Don't report timeout errors (expected in production)
        if exc_type.__name__ == "TimeoutError":
            return None

        # Don't report connection errors (transient)
        if exc_type.__name__ in ("ConnectionError", "ConnectionRefusedError"):
            return None

    return event


def capture_exception(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: str = "error"
) -> Optional[str]:
    """
    Capture an exception and send to Sentry.

    Args:
        exception: The exception to capture
        context: Additional context (bookmaker, sport, etc.)
        level: Error level (error, warning, info)

    Returns:
        Event ID if captured, None otherwise
    """
    if not SENTRY_AVAILABLE:
        return None

    try:
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_tag(key, str(value))
                scope.set_context("scrape_context", context)
            scope.set_level(level)
            return sentry_sdk.capture_exception(exception)
    except Exception as e:
        logger.error(f"Failed to capture exception to Sentry: {e}")
        return None


def capture_message(
    message: str,
    level: str = "info",
    context: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Capture a message and send to Sentry.

    Args:
        message: The message to capture
        level: Message level (error, warning, info)
        context: Additional context

    Returns:
        Event ID if captured, None otherwise
    """
    if not SENTRY_AVAILABLE:
        return None

    try:
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_tag(key, str(value))
                scope.set_context("message_context", context)
            scope.set_level(level)
            return sentry_sdk.capture_message(message)
    except Exception as e:
        logger.error(f"Failed to capture message to Sentry: {e}")
        return None


def set_user(user_id: str, email: Optional[str] = None) -> None:
    """Set user context for Sentry events."""
    if SENTRY_AVAILABLE:
        sentry_sdk.set_user({"id": user_id, "email": email})


def add_breadcrumb(
    message: str,
    category: str = "scraping",
    level: str = "info",
    data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Add a breadcrumb for debugging.

    Breadcrumbs are trail of events leading up to an error.
    """
    if SENTRY_AVAILABLE:
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {}
        )


# Context manager for scraper operations
class SentrySpan:
    """Context manager for Sentry performance spans."""

    def __init__(self, op: str, description: str):
        self.op = op
        self.description = description
        self.span = None

    def __enter__(self):
        if SENTRY_AVAILABLE:
            self.span = sentry_sdk.start_span(op=self.op, description=self.description)
            return self.span
        return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            self.span.finish()
        return False
