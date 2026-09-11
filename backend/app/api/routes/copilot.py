"""Copilot API routes: LangGraph ingestion, SSE streaming, document upload, and AI interactions."""
import json
import uuid
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status, Request, UploadFile, File, Form
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.complaint import Complaint, AuditLog, ChatMessage
from app.models.enums import ComplaintStatus, SeverityLevel, PriorityLevel, AuditActor, ChatRole
from app.schemas.complaint import IngestTextRequest, ComplaintResponse, ChatRequest
from app.agents.graph import stream_complaint_intake
from app.agents.nodes.correction_node import execute_correction

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


@router.post("/chat")
async def copilot_chat(payload: ChatRequest):
    """
    Phase 5: Conversational Correction Loop.
    Interprets follow-up chat messages, diffs fields against current complaint state,
    patches the database record, records immutable audit_log rows, and confirms the change.
    """
    async with AsyncSessionLocal() as db:
        # 1. Fetch complaint
        query = select(Complaint).where(Complaint.id == payload.complaint_id)
        result = await db.execute(query)
        complaint = result.scalar_one_or_none()

        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint '{payload.complaint_id}' not found.",
            )

        # 2. Check immutability guard
        if complaint.status == ComplaintStatus.committed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Committed complaints cannot be modified per 21 CFR 211.198 audit rules.",
            )

        # 3. Log user message in chat_messages table
        user_msg = ChatMessage(
            complaint_id=complaint.id,
            session_id=payload.session_id,
            role=ChatRole.user,
            content=payload.message,
        )
        db.add(user_msg)
        await db.flush()

        # 4. Extract current complaint dict with clean string values for enums and dates
        valid_cols = {c.name for c in Complaint.__table__.columns}
        current_data = {}
        for c in valid_cols:
            val = getattr(complaint, c)
            if hasattr(val, "value"):
                current_data[c] = val.value
            elif hasattr(val, "isoformat"):
                current_data[c] = val.isoformat()
            else:
                current_data[c] = val

        # 5. Run correction node
        correction_result = execute_correction(
            current_complaint=current_data,
            user_message=payload.message,
        )

        diffs = correction_result.get("diffs", [])
        reply = correction_result.get("reply", "")
        updated_fields = correction_result.get("updated_fields", {})

        # 6. Apply diffs and record audit log entries
        if correction_result.get("is_correction") and diffs:
            for d in diffs:
                field = d["field"]
                new_val = d["new_value"]
                old_val = d["old_value"]

                # Convert / normalize field value for ORM
                orm_val = new_val
                if field in ["manufacturing_date", "expiry_date", "complaint_date"]:
                    if isinstance(new_val, str) and new_val.strip():
                        try:
                            orm_val = datetime.strptime(new_val.strip(), "%Y-%m-%d").date()
                        except ValueError:
                            orm_val = None
                    else:
                        orm_val = None
                elif field in ["severity_suggested", "severity_final"]:
                    try:
                        orm_val = SeverityLevel(new_val)
                    except ValueError:
                        pass
                elif field == "priority":
                    try:
                        orm_val = PriorityLevel(new_val)
                    except ValueError:
                        pass

                setattr(complaint, field, orm_val)

                # Write audit trail row
                audit_entry = AuditLog(
                    complaint_id=complaint.id,
                    actor=AuditActor.user,
                    field_name=field,
                    old_value=str(old_val) if old_val is not None else None,
                    new_value=str(new_val) if new_val is not None else None,
                    source_message=payload.message,
                )
                db.add(audit_entry)

        # 7. Log assistant reply in chat_messages table
        assistant_msg = ChatMessage(
            complaint_id=complaint.id,
            session_id=payload.session_id,
            role=ChatRole.assistant,
            content=reply,
        )
        db.add(assistant_msg)

        await db.commit()
        await db.refresh(complaint)

        return {
            "reply": reply,
            "is_correction": correction_result.get("is_correction", False),
            "diffs": diffs,
            "updated_fields": updated_fields,
            "complaint": ComplaintResponse.model_validate(complaint).model_dump(mode="json"),
        }
