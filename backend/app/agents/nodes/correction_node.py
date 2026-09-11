"""Correction Node: Interprets follow-up conversational messages to diff, update, and confirm complaint fields."""
import json
import logging
from typing import Dict, Any, List, Optional
from groq import Groq

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_CORRECTION_FIELDS = {
    "complaint_source",
    "customer_name",
    "product_name",
    "product_strength_grade",
    "batch_lot_number",
    "manufacturing_date",
    "expiry_date",
    "affected_quantity",
    "originating_site_block",
    "impacted_npm",
    "complaint_category",
    "complaint_date",
    "complaint_description",
    "severity_suggested",
    "severity_final",
    "priority",
    "suggested_next_action",
}

CORRECTION_SYSTEM_PROMPT = """You are an AI Quality Assurance Assistant for an enterprise Pharmaceutical Quality Management System (QMS) governed by 21 CFR 211.198 and ICH Q10.

The user is reviewing an in-progress Customer Complaint draft and has sent a conversational chat message.

Your objectives:
1. Determine if the user message is requesting a CORRECTION or UPDATE to one or more fields in the complaint draft (e.g., "the batch number is actually BMX99202", "change customer to Apollo Pharmacy", "make severity Critical", "update quantity to 10 vials").
2. Or if the user is asking a QUESTION or GENERAL INQUIRY about the complaint draft (e.g., "what is the severity?", "why is this a packaging defect?", "summarize the risk").

Allowed field names for correction:
- complaint_source (Pharmacy, Email, Distributor, Phone, Portal, Other)
- customer_name
- product_name
- product_strength_grade (e.g. 500mg, 10mg/mL)
- batch_lot_number (e.g. BMX240601)
- manufacturing_date (YYYY-MM-DD)
- expiry_date (YYYY-MM-DD or null)
- affected_quantity (e.g. 48 capsules, 25 kg)
- originating_site_block
- impacted_npm
- complaint_category (Discoloration, Packaging Defect, Contamination, Labeling Defect, Efficacy, Sterility, etc.)
- complaint_date (YYYY-MM-DD)
- complaint_description
- severity_suggested (Critical, Major, Minor)
- priority (High, Medium, Low)

Output Format:
You must respond with ONLY a valid JSON object matching this exact structure:
{
  "is_correction": boolean,
  "diffs": [
    {
      "field": "<allowed_field_name>",
      "old_value": "<current_value_or_null>",
      "new_value": "<new_value_extracted_from_user_message>"
    }
  ],
  "reply": "<natural, concise, professional confirmation or answer to the user>"
}

Examples:
User: "actually the batch number is BMX99202"
Current State: {"batch_lot_number": "MET99201"}
Output:
{
  "is_correction": true,
  "diffs": [
    {"field": "batch_lot_number", "old_value": "MET99201", "new_value": "BMX99202"}
  ],
  "reply": "Updated batch number from MET99201 to BMX99202."
}

User: "Why is this classified as Major severity?"
Output:
{
  "is_correction": false,
  "diffs": [],
  "reply": "The complaint was categorized as Major severity because defective blister packaging compromises barrier integrity and may expose tablets to humidity, creating potential stability and dissolution risks."
}

Do NOT output markdown blocks (no ```json ... ```), just the pure JSON string.
"""


def execute_correction(
    current_complaint: Dict[str, Any],
    user_message: str,
) -> Dict[str, Any]:
    """
    Parses a user chat message against current complaint state.
    Returns:
      {
        "is_correction": bool,
        "diffs": List[Dict[str, Any]],
        "updated_fields": Dict[str, Any],
        "reply": str,
      }
    """
    client = Groq(api_key=settings.groq_api_key)
    model = settings.groq_model_extract

    # Serialize complaint state concisely
    state_summary = {
        k: (str(v) if v is not None else None)
        for k, v in current_complaint.items()
        if k in ALLOWED_CORRECTION_FIELDS
    }

    user_prompt = (
        f"CURRENT COMPLAINT STATE:\n{json.dumps(state_summary, indent=2)}\n\n"
        f"USER MESSAGE:\n\"{user_message}\"\n\n"
        f"Analyze intent and return JSON diff/reply:"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=800,
        )
        content = (response.choices[0].message.content or "").strip()

        # Clean any accidental markdown fence
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        parsed = json.loads(content)
    except Exception as e:
        logger.error(f"Correction node parsing failed: {e}")
        # Graceful fallback: basic regex/keyword matching or friendly reply
        return {
            "is_correction": False,
            "diffs": [],
            "updated_fields": {},
            "reply": f"I received your message: '{user_message}'. Please specify the exact field and new value if you wish to correct the complaint.",
        }

    is_correction = bool(parsed.get("is_correction", False))
    raw_diffs = parsed.get("diffs", [])
    valid_diffs: List[Dict[str, Any]] = []
    updated_fields: Dict[str, Any] = {}

    for d in raw_diffs:
        field = d.get("field")
        if field in ALLOWED_CORRECTION_FIELDS:
            old_val = state_summary.get(field)
            new_val = d.get("new_value")
            if new_val is not None:
                new_val_str = str(new_val).strip()
                if old_val != new_val_str:
                    valid_diffs.append({
                        "field": field,
                        "old_value": old_val,
                        "new_value": new_val_str,
                    })
                    updated_fields[field] = new_val_str

    reply = parsed.get("reply") or (
        f"Updated {len(valid_diffs)} field(s) in the complaint draft."
        if valid_diffs
        else "No modifications were required."
    )

    return {
        "is_correction": len(valid_diffs) > 0,
        "diffs": valid_diffs,
        "updated_fields": updated_fields,
        "reply": reply,
    }
