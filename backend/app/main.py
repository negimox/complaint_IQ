from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.routes import complaints, copilot


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all tables and ensure schema additions on startup."""
    async with engine.begin() as conn:
        from sqlalchemy import text
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        except Exception:
            pass
        await conn.run_sync(Base.metadata.create_all)
        # Ensure Phase 6 columns exist on complaints table
        await conn.execute(text("ALTER TABLE complaints ADD COLUMN IF NOT EXISTS complaint_summary VARCHAR(300);"))
        await conn.execute(text("ALTER TABLE complaints ADD COLUMN IF NOT EXISTS capa_recommendation TEXT;"))
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI-Powered Customer Complaint Management System for Pharmaceutical QMS",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(complaints.router, prefix="/complaints", tags=["complaints"])
app.include_router(copilot.router, prefix="/copilot", tags=["copilot"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": settings.app_name}
