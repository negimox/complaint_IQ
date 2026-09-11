"""Validator node: rule-based integrity, chronology, and completeness checks."""
from datetime import datetime
from typing import Dict, Any, List
from app.agents.state import ComplaintGraphState

REQUIRED_QMS_FIELDS = [
    ("customer_name", "Customer / Reporting Entity"),
    ("product_name", "Product Name"),
    ("batch_lot_number", "Batch / Lot Number"),
    ("complaint_category", "Complaint Category"),
    ("affected_quantity", "Affected Quantity"),
]


def validator_node(state: ComplaintGraphState) -> Dict[str, Any]:
    """Validates extracted entity data against pharma QMS integrity rules."""
    extracted = state.get("extracted_data", {})
    validation_errors: List[str] = []
    missing_fields: List[str] = []

    # 1. Required fields check
    for field_key, field_label in REQUIRED_QMS_FIELDS:
        val = extracted.get(field_key)
        if not val or (isinstance(val, str) and not val.strip()):
            missing_fields.append(field_label)

    # 2. Date chronology and validity check
    mfg_str = extracted.get("manufacturing_date")
    exp_str = extracted.get("expiry_date")
    complaint_date_str = extracted.get("complaint_date")

    mfg_date = None
    exp_date = None

    if mfg_str:
        try:
            mfg_date = datetime.strptime(mfg_str, "%Y-%m-%d").date()
        except ValueError:
            validation_errors.append(f"Manufacturing date '{mfg_str}' is not valid ISO YYYY-MM-DD format.")

    if exp_str:
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
        except ValueError:
            validation_errors.append(f"Expiry date '{exp_str}' is not valid ISO YYYY-MM-DD format.")

    if mfg_date and exp_date:
        if mfg_date >= exp_date:
            validation_errors.append(
                f"Chronological violation: Manufacturing date ({mfg_str}) must precede Expiry date ({exp_str})."
            )

    # 3. Expiry check against complaint date
    if exp_date and complaint_date_str:
        try:
            c_date = datetime.strptime(complaint_date_str, "%Y-%m-%d").date()
            if c_date > exp_date:
                # Expired product complaint is notable for investigation
                validation_errors.append(
                    f"Notice: Product was reported past its labelled expiry date ({exp_str})."
                )
        except ValueError:
            pass

    is_valid = len(validation_errors) == 0

    if is_valid and not missing_fields:
        status_msg = "Data integrity checks passed with all core QMS fields present."
    elif missing_fields:
        status_msg = f"Data verified with {len(missing_fields)} optional/missing fields: {', '.join(missing_fields[:3])}."
    else:
        status_msg = f"Validation flagged {len(validation_errors)} items for QA review."

    return {
        "validation_errors": validation_errors,
        "missing_fields": missing_fields,
        "is_valid": is_valid,
        "step": "validator",
        "progress": 55,
        "status_message": status_msg,
    }
