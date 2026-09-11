"""
Copilot routes — placeholder for Phase 3+.
POST /copilot/ingest  — text/file intake (Phase 3–4)
POST /copilot/chat    — conversational correction (Phase 5)
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def copilot_status():
    """Health check for the copilot service."""
    return {"status": "ready", "message": "LangGraph pipeline coming in Phase 3"}
