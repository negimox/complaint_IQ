import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Text, Date, DateTime, Enum as SAEnum,
    ForeignKey, func, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.models.enums import (
    ComplaintStatus, SeverityLevel, PriorityLevel,
    ComplaintSource, AuditActor, ChatRole
)


def generate_complaint_id() -> str:
    """Generate human-readable complaint ID: CC-YYYY-NNNNN."""
    year = datetime.utcnow().year
    uid = str(uuid.uuid4().int)[:5]
    return f"CC-{year}-{uid}"


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(String(20), primary_key=True, default=generate_complaint_id)
    status = Column(
        SAEnum(ComplaintStatus, name="complaint_status"),
        nullable=False,
        default=ComplaintStatus.pending_triage,
    )

    # ── Section 1: Origin & Customer Details ──────────────────────────────────
    complaint_source = Column(String(50), nullable=True)
    customer_name = Column(String(255), nullable=True)

    # ── Section 2: Product & Batch Identification ──────────────────────────────
    product_name = Column(String(255), nullable=True)
    product_strength_grade = Column(String(100), nullable=True)
    batch_lot_number = Column(String(100), nullable=True)
    manufacturing_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    affected_quantity = Column(String(100), nullable=True)  # free-text: "48 capsules"

    # ── Section 3: Complaint Details ───────────────────────────────────────────
    originating_site_block = Column(String(200), nullable=True)  # pharma-specific
    impacted_npm = Column(Text, nullable=True)                    # Non-Product Materials
    complaint_category = Column(String(100), nullable=True)
    complaint_date = Column(Date, nullable=True)
    complaint_description = Column(Text, nullable=True)          # AI-synthesized, user-editable

    # ── Section 4: Initial Assessment & Priority ───────────────────────────────
    severity_suggested = Column(
        SAEnum(SeverityLevel, name="severity_level"),
        nullable=True,
        default=SeverityLevel.not_assessed,
    )
    severity_final = Column(
        SAEnum(SeverityLevel, name="severity_level_final"),
        nullable=True,
    )
    priority = Column(
        SAEnum(PriorityLevel, name="priority_level"),
        nullable=True,
        default=PriorityLevel.not_assessed,
    )
    suggested_next_action = Column(Text, nullable=True)
    initial_risk_assessment = Column(Text, nullable=True)  # AI rationale paragraph

    # ── Audit / Source ─────────────────────────────────────────────────────────
    raw_source_text = Column(Text, nullable=True)          # original pasted text
    raw_source_file_path = Column(String(500), nullable=True)

    # ── Bonus Features ─────────────────────────────────────────────────
    complaint_summary = Column(String(300), nullable=True)   # ≤25-word AI summary for list/dashboard
    capa_recommendation = Column(Text, nullable=True)        # AI CAPA type + actions (ICH Q10 rubric)
    # pgvector embedding (384-dim) for duplicate detection
    embedding = Column(Vector(384), nullable=True)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    committed_at = Column(DateTime(timezone=True), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    audit_logs = relationship("AuditLog", back_populates="complaint", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="complaint", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id = Column(String(20), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    actor = Column(SAEnum(AuditActor, name="audit_actor"), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    source_message = Column(Text, nullable=True)  # the chat text that caused the change
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    complaint = relationship("Complaint", back_populates="audit_logs")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id = Column(String(20), ForeignKey("complaints.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(100), nullable=True)  # pre-commit session tracking
    role = Column(SAEnum(ChatRole, name="chat_role"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    complaint = relationship("Complaint", back_populates="chat_messages")
