# apps/api/src/api/main.py
import json
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from api.routers import auth

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

# Log startup configuration
@app.on_event("startup")
async def startup_event():
    logger.info("Starting MB API")
    logger.info(f"CORS Origins: {cors_origins}")
    logger.info(f"Auth Audience: {os.getenv('MB_AUTH_AUDIENCE')}")
    logger.info(f"Auth JWKS URL: {os.getenv('MB_AUTH_JWKS_URL')}")
    logger.info(f"Clerk Issuer: {os.getenv('CLERK_ISSUER')}")