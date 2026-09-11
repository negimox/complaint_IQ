"""LangGraph state definition for ComplaintIQ ingestion and triage pipeline."""
from typing import TypedDict, Optional, Dict, Any, List


class ComplaintGraphState(TypedDict, total=False):
    # Inputs
    raw_text: str
    file_path: Optional[str]
    input_type: str  # "text" | "file"
    complaint_id: Optional[str]
    session_id: Optional[str]

    # Node outputs
    extracted_data: Dict[str, Any]
    validation_errors: List[str]
    missing_fields: List[str]
    is_valid: bool
    synthesized_description: str
    risk_assessment: Dict[str, Any]

    # Final combined record
    final_complaint: Dict[str, Any]

    # Pipeline progress tracking (for SSE)
    step: str
    progress: int
    status_message: str
