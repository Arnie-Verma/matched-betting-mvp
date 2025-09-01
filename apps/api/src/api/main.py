from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.config import settings
from api.routers import health

app = FastAPI(title="matched-betting-mvp API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router)

@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
