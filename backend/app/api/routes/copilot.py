"""Copilot API routes: LangGraph ingestion, SSE streaming, document upload, and AI interactions."""
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status, Request, UploadFile, File, Form
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.complaint import Complaint, AuditLog, ChatMessage
from app.models.enums import ComplaintStatus, SeverityLevel, PriorityLevel, AuditActor, ChatRole
from app.schemas.complaint import IngestTextRequest, ComplaintResponse
from app.agents.graph import stream_complaint_intake

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def _normalize_dict_for_orm(data: Dict[str, Any]) -> Dict[str, Any]:
    """Converts string dates and enum representations into ORM-compatible objects."""
    res = dict(data)
    for date_field in ["manufacturing_date", "expiry_date", "complaint_date"]:
        val = res.get(date_field)
        if isinstance(val, str) and val.strip():
            try:
                res[date_field] = datetime.strptime(val.strip(), "%Y-%m-%d").date()
            except ValueError:
                res[date_field] = None

    if "severity_suggested" in res and isinstance(res["severity_suggested"], str):
        try:
            res["severity_suggested"] = SeverityLevel(res["severity_suggested"])
        except ValueError:
            res["severity_suggested"] = SeverityLevel.not_assessed

    if "severity_final" in res and isinstance(res["severity_final"], str):
        try:
            res["severity_final"] = SeverityLevel(res["severity_final"])
        except ValueError:
            res["severity_final"] = None

    if "priority" in res and isinstance(res["priority"], str):
        try:
            res["priority"] = PriorityLevel(res["priority"])
        except ValueError:
            res["priority"] = PriorityLevel.not_assessed

    if "status" in res and isinstance(res["status"], str):
        try:
            res["status"] = ComplaintStatus(res["status"])
        except ValueError:
            res["status"] = ComplaintStatus.pending_triage

    return res


async def _save_or_update_complaint(
    complaint_id: Optional[str],
    final_complaint_data: Dict[str, Any],
    raw_text: str,
    file_path: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Complaint:
    """Persists or updates the complaint record in the database upon intake completion."""
    async with AsyncSessionLocal() as db:
        orm_data = _normalize_dict_for_orm(final_complaint_data)
        orm_data["raw_source_text"] = raw_text
        if file_path:
            orm_data["raw_source_file_path"] = file_path

        # Only pass valid model columns
        valid_cols = {c.name for c in Complaint.__table__.columns}
        filtered_data = {k: v for k, v in orm_data.items() if k in valid_cols}

        complaint: Optional[Complaint] = None

        if complaint_id:
            query = select(Complaint).where(Complaint.id == complaint_id)
            result = await db.execute(query)
            complaint = result.scalar_one_or_none()
            if complaint and complaint.status == ComplaintStatus.committed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Committed complaints cannot be modified.",
                )

        if not complaint:
            complaint = Complaint(**filtered_data)
            db.add(complaint)
            await db.flush()
        else:
            for k, v in filtered_data.items():
                setattr(complaint, k, v)

        # Record AuditLog for AI ingestion
        audit = AuditLog(
            complaint_id=complaint.id,
            actor=AuditActor.ai,
            field_name="intake_pipeline",
            old_value=None,
            new_value=complaint.status.value,
            source_message=(f"Document: {Path(file_path).name}" if file_path else (raw_text[:200] if raw_text else None)),
        )
        db.add(audit)

        # Record assistant summary message in chat history
        source_desc = f"'{Path(file_path).name}'" if file_path else "the submitted intake"
        summary_msg = (
            f"Extracted details from {source_desc} for {complaint.product_name or 'the product'} "
            f"(Lot: {complaint.batch_lot_number or 'N/A'}, Customer: {complaint.customer_name or 'N/A'}). "
            f"Categorized as '{complaint.complaint_category or 'General'}' with "
            f"suggested severity '{complaint.severity_suggested.value if complaint.severity_suggested else 'Not Assessed'}'. "
            f"Review the populated fields and commit when ready."
        )
        chat_msg = ChatMessage(
            complaint_id=complaint.id,
            session_id=session_id,
            role=ChatRole.assistant,
            content=summary_msg,
        )
        db.add(chat_msg)

        await db.commit()
        await db.refresh(complaint)
        return complaint


@router.get("/status")
async def copilot_status():
    """Health check for the copilot service."""
    return {"status": "ready", "pipeline": "LangGraph multi-agent intake active (Text + Document Ingestion)"}


@router.post("/ingest")
async def ingest_complaint_stream(request: Request):
    """
    Universal intake endpoint: accepts BOTH application/json (raw text) AND
    multipart/form-data (file uploads). Streams progress via Server-Sent Events (SSE).
    """
    content_type = request.headers.get("content-type", "")
    raw_text = ""
    file_path: Optional[str] = None
    complaint_id: Optional[str] = None
    session_id: Optional[str] = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        complaint_id = form.get("complaint_id")
        session_id = form.get("session_id")
        raw_text = form.get("text") or ""

        if uploaded_file and hasattr(uploaded_file, "filename") and uploaded_file.filename:
            safe_filename = f"{uuid.uuid4().hex}_{Path(uploaded_file.filename).name}"
            dest = UPLOAD_DIR / safe_filename
            content = await uploaded_file.read()
            dest.write_bytes(content)
            file_path = str(dest)
    else:
        try:
            body = await request.json()
            raw_text = body.get("text", "")
            complaint_id = body.get("complaint_id")
            session_id = body.get("session_id")
        except Exception:
            raw_text = ""

    async def event_generator():
        saved_complaint: Optional[Complaint] = None

        async for event in stream_complaint_intake(
            raw_text=raw_text,
            complaint_id=complaint_id,
            session_id=session_id,
            file_path=file_path,
        ):
            if await request.is_disconnected():
                logger.info("Client disconnected from SSE intake stream.")
                break

            # If final node completed, persist to DB and attach record
            if event.get("step") == "risk_assessor" and event.get("final_complaint"):
                try:
                    final_raw = raw_text or event.get("raw_text", "")
                    saved_complaint = await _save_or_update_complaint(
                        complaint_id=complaint_id,
                        final_complaint_data=event["final_complaint"],
                        raw_text=final_raw,
                        file_path=file_path,
                        session_id=session_id,
                    )
                    event["complaint_id"] = saved_complaint.id
                    event["complaint"] = ComplaintResponse.model_validate(saved_complaint).model_dump(mode="json")
                except Exception as e:
                    logger.error(f"Failed to persist complaint during intake: {e}")
                    event["save_error"] = str(e)

            yield {
                "event": "message",
                "data": json.dumps(event, default=str),
            }

    return EventSourceResponse(event_generator())


@router.post("/upload")
async def upload_document_stream(
    request: Request,
    file: UploadFile = File(...),
    complaint_id: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
):
    """
    Dedicated multipart file upload endpoint.
    Extracts text/tables and streams SSE progress through LangGraph.
    """
    safe_filename = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    dest = UPLOAD_DIR / safe_filename
    content = await file.read()
    dest.write_bytes(content)
    file_path = str(dest)

    async def event_generator():
        saved_complaint: Optional[Complaint] = None

        async for event in stream_complaint_intake(
            raw_text="",
            complaint_id=complaint_id,
            session_id=session_id,
            file_path=file_path,
        ):
            if await request.is_disconnected():
                break

            if event.get("step") == "risk_assessor" and event.get("final_complaint"):
                try:
                    saved_complaint = await _save_or_update_complaint(
                        complaint_id=complaint_id,
                        final_complaint_data=event["final_complaint"],
                        raw_text=event.get("raw_text", ""),
                        file_path=file_path,
                        session_id=session_id,
                    )
                    event["complaint_id"] = saved_complaint.id
                    event["complaint"] = ComplaintResponse.model_validate(saved_complaint).model_dump(mode="json")
                except Exception as e:
                    logger.error(f"Failed to persist complaint during file upload: {e}")
                    event["save_error"] = str(e)

            yield {
                "event": "message",
                "data": json.dumps(event, default=str),
            }

    return EventSourceResponse(event_generator())


@router.post("/ingest/sync", response_model=ComplaintResponse)
async def ingest_complaint_text_sync(payload: IngestTextRequest):
    """Synchronous intake endpoint for direct REST execution without SSE streaming."""
    last_event: Dict[str, Any] = {}
    async for event in stream_complaint_intake(
        raw_text=payload.text,
        complaint_id=payload.complaint_id,
        session_id=payload.session_id,
    ):
        last_event = event

    final_data = last_event.get("final_complaint", {})
    if not final_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pipeline failed to extract complaint data.",
        )

    complaint = await _save_or_update_complaint(
        complaint_id=payload.complaint_id,
        final_complaint_data=final_data,
        raw_text=payload.text,
        session_id=payload.session_id,
    )
    return complaint
