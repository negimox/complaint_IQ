from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.models.complaint import Complaint, AuditLog
from app.models.enums import ComplaintStatus, AuditActor
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintUpdate,
    ComplaintResponse,
    ComplaintListItem,
    AuditLogResponse,
    CommitResponse,
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
