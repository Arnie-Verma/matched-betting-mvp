# apps/api/src/api/main.py
import json
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from api.routers import auth, billing, stripe_webhooks, plan_demo, odds_matcher, odds_matcher_mock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MB API", version="0.1.0")

# CORS configuration
cors_origins = json.loads(os.getenv("CORS_ORIGINS", '["http://localhost:3000"]'))
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# Include routers
app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(stripe_webhooks.router)
app.include_router(plan_demo.router)
app.include_router(odds_matcher.router)
app.include_router(odds_matcher_mock.router)  # Mock data for testing - DELETE when scraping works!

# Log startup configuration
@app.on_event("startup")
async def startup_event():
    logger.info("Starting MB API")
    logger.info(f"CORS Origins: {cors_origins}")
    logger.info(f"Auth Audience: {os.getenv('MB_AUTH_AUDIENCE')}")
    logger.info(f"Auth JWKS URL: {os.getenv('MB_AUTH_JWKS_URL')}")
    logger.info(f"Clerk Issuer: {os.getenv('CLERK_ISSUER')}")

    # Run database migrations automatically on startup (development only)
    if os.getenv("ENVIRONMENT", "development") == "development":
        logger.info("Running database migrations...")
        try:
            from alembic.config import Config
            from alembic import command
            import sys
            from pathlib import Path

            # Get alembic config
            alembic_cfg = Config(str(Path(__file__).parent.parent.parent / "alembic.ini"))
            alembic_cfg.set_main_option("script_location", str(Path(__file__).parent.parent.parent / "alembic"))

            # Run migrations
            command.upgrade(alembic_cfg, "head")
            logger.info("✅ Database migrations completed successfully")
        except Exception as e:
            logger.error(f"❌ Database migration failed: {e}")
            # Don't fail startup - let it continue for now
            # In production, you might want to fail here