from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.models.complaint import Complaint, AuditLog, ChatMessage
from app.models.enums import ComplaintStatus, AuditActor
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintUpdate,
    ComplaintResponse,
    ComplaintListItem,
    AuditLogResponse,
    CommitResponse,
    ChatMessageResponse,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(complaint_id: str, db: AsyncSession) -> Complaint:
    result = await db.execute(select(Complaint).where(Complaint.id == complaint_id))
    complaint = result.scalar_one_or_none()
    if not complaint:
        raise HTTPException(status_code=404, detail=f"Complaint '{complaint_id}' not found")
    return complaint


def _assert_not_committed(complaint: Complaint) -> None:
    if complaint.status == ComplaintStatus.committed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Committed complaints cannot be modified.",
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ComplaintResponse, status_code=201)
async def create_complaint(
    payload: ComplaintCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new draft complaint (pre-AI population)."""
    complaint = Complaint(**payload.model_dump(exclude_none=True))
    db.add(complaint)
    await db.commit()
    await db.refresh(complaint)
    return complaint


@router.get("/", response_model=List[ComplaintListItem])
async def list_complaints(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all complaints, newest first."""
    result = await db.execute(
        select(Complaint).order_by(desc(Complaint.created_at)).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{complaint_id}", response_model=ComplaintResponse)
async def get_complaint(
    complaint_id: str,
    db: AsyncSession = Depends(get_db),
):
    return await _get_or_404(complaint_id, db)


@router.patch("/{complaint_id}", response_model=ComplaintResponse)
async def update_complaint(
    complaint_id: str,
    payload: ComplaintUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partial update — rejected for committed complaints."""
    complaint = await _get_or_404(complaint_id, db)
    _assert_not_committed(complaint)

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(complaint, field, value)

    await db.commit()
    await db.refresh(complaint)
    return complaint


@router.patch("/{complaint_id}/commit", response_model=CommitResponse)
async def commit_complaint(
    complaint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Commit a complaint to the QMS Ledger — irreversible.
    Pre-commit validates required fields, locks the record, writes audit trail.
    """
    complaint = await _get_or_404(complaint_id, db)
    _assert_not_committed(complaint)

    # ── Pre-commit validation ─────────────────────────────────────────────────
    required_fields = [
        "customer_name", "product_name", "batch_lot_number",
        "complaint_category", "complaint_description",
    ]
    missing = [f for f in required_fields if not getattr(complaint, f)]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Cannot commit: required fields are missing.",
                "missing_fields": missing,
            },
        )

    # ── Status transition ─────────────────────────────────────────────────────
    old_status = complaint.status.value
    complaint.status = ComplaintStatus.committed
    complaint.committed_at = datetime.utcnow()

    # ── Severity finalization ─────────────────────────────────────────────────
    if not complaint.severity_final and complaint.severity_suggested:
        complaint.severity_final = complaint.severity_suggested

    # ── Audit trail ───────────────────────────────────────────────────────────
    audit_entry = AuditLog(
        complaint_id=complaint.id,
        actor=AuditActor.user,
        field_name="status",
        old_value=old_status,
        new_value=ComplaintStatus.committed.value,
        source_message="User committed complaint to QMS ledger",
    )
    db.add(audit_entry)

    await db.commit()
    await db.refresh(complaint)
    return CommitResponse(complaint=ComplaintResponse.model_validate(complaint))


@router.get("/{complaint_id}/audit-log", response_model=List[AuditLogResponse])
async def get_audit_log(
    complaint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the full audit trail for a complaint."""
    await _get_or_404(complaint_id, db)
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.complaint_id == complaint_id)
        .order_by(AuditLog.created_at)
    )
    return result.scalars().all()


# ── Phase 6: Chat History ─────────────────────────────────────────────────────────────

@router.get("/{complaint_id}/chat-messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    complaint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full chat history for a complaint, oldest first."""
    await _get_or_404(complaint_id, db)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.complaint_id == complaint_id)
        .order_by(ChatMessage.created_at)
    )
    return result.scalars().all()


# ── Phase 6: Completeness Checker ────────────────────────────────────────────────────

@router.get("/{complaint_id}/completeness")
async def check_completeness(
    complaint_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Server-authoritative QMS pre-commit completeness check.
    Returns structured checklist aligned with 21 CFR 211.198 / ICH Q10 required fields.
    """
    complaint = await _get_or_404(complaint_id, db)

    required_checks = [
        ("customer_name", "Origin & Customer Identification", "Source channel and reporting customer/entity recorded"),
        ("product_name", "Product Identification", "Pharmaceutical drug product name recorded"),
        ("batch_lot_number", "Batch / Lot Traceability", "Batch number specified for production recall & retention sample check"),
        ("manufacturing_date", "Manufacturing Date", "Valid manufacturing date; must precede expiry if provided"),
        ("affected_quantity", "Affected Quantity & Unit", "Quantity specified with measurable units (e.g. capsules, vials, kg)"),
        ("complaint_category", "QMS Defect Classification", "Defect category assigned (e.g., Contamination, Packaging, Efficacy)"),
        ("complaint_description", "Detailed Investigation Narrative", "Comprehensive description of defect (minimum 20 characters)"),
        ("severity_suggested", "Severity & Priority Assignment", "Criticality level and priority assessed for QA triage"),
    ]

    items = []
    for field, label, description in required_checks:
        val = getattr(complaint, field, None)
        if field == "complaint_description":
            passed = bool(val and len(str(val).strip()) >= 20)
        elif field == "severity_suggested":
            sev_ok = val and val.value not in ("Not Assessed", "not_assessed")
            pri_ok = complaint.priority and complaint.priority.value not in ("Not Assessed", "not_assessed")
            passed = bool(sev_ok and pri_ok)
        else:
            passed = bool(val and str(val).strip())
        items.append({"id": field, "label": label, "description": description, "passed": passed})

    passed_count = sum(1 for i in items if i["passed"])
    total = len(items)
    score = round((passed_count / total) * 100) if total else 0
    can_commit = passed_count == total

    return {
        "complaint_id": complaint_id,
        "score": score,
        "passed_checks": passed_count,
        "total_checks": total,
        "can_commit": can_commit,
        "items": items,
        "summary_message": (
            "All QMS integrity checks satisfied. Ready for immutable ledger commitment."
            if can_commit
            else f"{total - passed_count} required QMS {'check' if total - passed_count == 1 else 'checks'} remaining."
        ),
    }


# ── Phase 6: Duplicate Detection ──────────────────────────────────────────────────────

@router.get("/{complaint_id}/duplicates")
async def get_duplicate_complaints(
    complaint_id: str,
    threshold: float = 0.82,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Phase 6: Finds similar committed complaints using pgvector cosine similarity
    on complaint_description embeddings (sentence-transformers all-MiniLM-L6-v2).
    Also generates and stores the embedding if not yet computed.
    """
    from app.agents.nodes.duplicate_detector import generate_embedding, find_similar_complaints

    complaint = await _get_or_404(complaint_id, db)

    # Generate embedding if not yet stored
    if complaint.embedding is None and complaint.complaint_description:
        embedding_vec = generate_embedding(complaint.complaint_description)
        if embedding_vec:
            complaint.embedding = embedding_vec
            await db.commit()
            await db.refresh(complaint)
    elif complaint.embedding is None:
        return {
            "complaint_id": complaint_id,
            "duplicates": [],
            "message": "No complaint description available for similarity search.",
        }

    if complaint.embedding is None:
        return {
            "complaint_id": complaint_id,
            "duplicates": [],
            "message": "Embedding generation unavailable (sentence-transformers not installed).",
        }

    embedding_list = complaint.embedding if isinstance(complaint.embedding, list) else list(complaint.embedding)
    similar = await find_similar_complaints(
        db=db,
        embedding=embedding_list,
        exclude_id=complaint_id,
        threshold=threshold,
        limit=limit,
    )

    return {
        "complaint_id": complaint_id,
        "duplicates": similar,
        "count": len(similar),
        "threshold_used": threshold,
        "message": (
            f"Found {len(similar)} similar committed complaint(s)."
            if similar
            else "No similar committed complaints found above the similarity threshold."
        ),
    }
