from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
import uuid

from app.models.enums import (
    ComplaintStatus, SeverityLevel, PriorityLevel, AuditActor, ChatRole
)


# ── Complaint Schemas ──────────────────────────────────────────────────────────

class ComplaintCreate(BaseModel):
    """Used when creating a draft complaint."""
    complaint_source: Optional[str] = None
    customer_name: Optional[str] = None
    product_name: Optional[str] = None
    product_strength_grade: Optional[str] = None
    batch_lot_number: Optional[str] = None
    manufacturing_date: Optional[date] = None
    expiry_date: Optional[date] = None
    affected_quantity: Optional[str] = None
    originating_site_block: Optional[str] = None
    impacted_npm: Optional[str] = None
    complaint_category: Optional[str] = None
    complaint_date: Optional[date] = None
    complaint_description: Optional[str] = None
    severity_suggested: Optional[SeverityLevel] = None
    severity_final: Optional[SeverityLevel] = None
    priority: Optional[PriorityLevel] = None
    suggested_next_action: Optional[str] = None
    initial_risk_assessment: Optional[str] = None
    raw_source_text: Optional[str] = None


class ComplaintUpdate(BaseModel):
    """Partial update — all fields optional. Used by PATCH /complaints/{id}."""
    complaint_source: Optional[str] = None
    customer_name: Optional[str] = None
    product_name: Optional[str] = None
    product_strength_grade: Optional[str] = None
    batch_lot_number: Optional[str] = None
    manufacturing_date: Optional[date] = None
    expiry_date: Optional[date] = None
    affected_quantity: Optional[str] = None
    originating_site_block: Optional[str] = None
    impacted_npm: Optional[str] = None
    complaint_category: Optional[str] = None
    complaint_date: Optional[date] = None
    complaint_description: Optional[str] = None
    severity_suggested: Optional[SeverityLevel] = None
    severity_final: Optional[SeverityLevel] = None
    priority: Optional[PriorityLevel] = None
    suggested_next_action: Optional[str] = None
    initial_risk_assessment: Optional[str] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ComplaintUpdate":
        if self.manufacturing_date and self.expiry_date:
            if self.manufacturing_date >= self.expiry_date:
                raise ValueError("manufacturing_date must be before expiry_date")
        return self


class ComplaintResponse(BaseModel):
    """Full complaint record returned from the API."""
    id: str
    status: ComplaintStatus
    complaint_source: Optional[str]
    customer_name: Optional[str]
    product_name: Optional[str]
    product_strength_grade: Optional[str]
    batch_lot_number: Optional[str]
    manufacturing_date: Optional[date]
    expiry_date: Optional[date]
    affected_quantity: Optional[str]
    originating_site_block: Optional[str]
    impacted_npm: Optional[str]
    complaint_category: Optional[str]
    complaint_date: Optional[date]
    complaint_description: Optional[str]
    severity_suggested: Optional[SeverityLevel]
    severity_final: Optional[SeverityLevel]
    priority: Optional[PriorityLevel]
    suggested_next_action: Optional[str]
    initial_risk_assessment: Optional[str]
    raw_source_text: Optional[str]
    raw_source_file_path: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    committed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ComplaintListItem(BaseModel):
    """Minimal complaint summary for list views."""
    id: str
    status: ComplaintStatus
    customer_name: Optional[str]
    product_name: Optional[str]
    complaint_category: Optional[str]
    severity_suggested: Optional[SeverityLevel]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ── AI Extraction Schema ───────────────────────────────────────────────────────

class ComplaintExtraction(BaseModel):
    """
    Strict JSON schema the LLM must return during entity extraction.
    All fields nullable — never hallucinate, leave null if not found.
    """
    complaint_source: Optional[str] = Field(None, description="Source: Pharmacy, Email, Distributor, Phone, Portal, or Other")
    customer_name: Optional[str] = Field(None, description="Name of reporting customer or distributor")
    product_name: Optional[str] = Field(None, description="Name of the pharmaceutical product")
    product_strength_grade: Optional[str] = Field(None, description="Strength or grade, e.g. '500mg', 'Grade A'")
    batch_lot_number: Optional[str] = Field(None, description="Batch or lot number")
    manufacturing_date: Optional[str] = Field(None, description="Manufacturing date in YYYY-MM-DD format")
    expiry_date: Optional[str] = Field(None, description="Expiry date in YYYY-MM-DD format or null")
    affected_quantity: Optional[str] = Field(None, description="Affected quantity with unit, e.g. '48 capsules', '25 kg'")
    originating_site_block: Optional[str] = Field(None, description="Manufacturing site/block if mentioned")
    impacted_npm: Optional[str] = Field(None, description="Non-product materials affected, if any")
    complaint_category: Optional[str] = Field(None, description="Category: Contamination, Discoloration, Packaging, Labeling, Efficacy, Sterility, Other")
    complaint_date: Optional[str] = Field(None, description="Date complaint was received, YYYY-MM-DD")
    raw_complaint_text: Optional[str] = Field(None, description="Full original complaint text for synthesis")


# ── Audit Log Schemas ──────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: uuid.UUID
    complaint_id: str
    actor: AuditActor
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    source_message: Optional[str]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Chat Message Schemas ───────────────────────────────────────────────────────

class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    complaint_id: Optional[str]
    session_id: Optional[str]
    role: ChatRole
    content: str
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Copilot / Ingest Schemas ───────────────────────────────────────────────────

class IngestTextRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Raw complaint text to extract from")
    complaint_id: Optional[str] = Field(None, description="Existing complaint ID to update, or null to create new")
    session_id: Optional[str] = Field(None, description="Session ID for pre-commit tracking")


class ChatRequest(BaseModel):
    complaint_id: str
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None


class CommitResponse(BaseModel):
    complaint: ComplaintResponse
    message: str = "Complaint successfully committed to QMS ledger."
