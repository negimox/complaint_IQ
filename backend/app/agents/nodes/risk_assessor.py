"""Risk Assessor node: evaluates severity, priority, and containment actions using Groq LLM."""
import json
import logging
from typing import Dict, Any
from groq import Groq
from app.core.config import settings
from app.agents.state import ComplaintGraphState
from app.models.enums import SeverityLevel, PriorityLevel

logger = logging.getLogger(__name__)

RISK_ASSESSMENT_PROMPT = """You are a senior Quality Assurance Director and Risk Management Expert in the pharmaceutical industry operating under ICH Q9 (Quality Risk Management) and ICH Q10 / 21 CFR 211 standards.

Evaluate the complaint and provide a structured risk classification adhering to this strict rubric:

SEVERITY RUBRIC:
- "Critical":
  * Defects that could cause death, life-threatening harm, or permanent injury.
  * Sterility assurance failure, microbial contamination, presence of glass/metal particulate matter.
  * Product mix-up (wrong active pharmaceutical ingredient, wrong dosage in packaging).
  * Extreme sub-potency or super-potency in narrow therapeutic index drugs.
- "Major":
  * Defects that may cause illness, temporary impairment, or improper dosing.
  * Physical or chemical degradation of the dosage form (capsule/tablet discoloration, precipitation, cracking, dissolution failure, caking). Any discoloration of the actual drug product is MAJOR, never minor.
  * Compromised primary container integrity (leaking vials, compromised induction seal).
  * Out-of-specification assay or stability failure.
- "Minor":
  * Cosmetic defects that do not impact patient safety, product efficacy, or dosage accuracy.
  * Secondary carton scuffs, minor labeling print smudges, non-functional outer packaging imperfections.

PRIORITY RUBRIC:
- "High": Critical severity, potential batch recall trigger, or high distribution volume exposure.
- "Medium": Major severity requiring standard 30-day investigation and retained sample inspection.
- "Low": Minor cosmetic defect addressed via routine trend monitoring.

Return ONLY a valid JSON object matching this schema:
{
  "severity_suggested": "Critical" | "Major" | "Minor",
  "priority": "High" | "Medium" | "Low",
  "suggested_next_action": "Concrete operational containment steps (e.g., quarantine retain samples, initiate OOS investigation, request return of complaint sample)",
  "initial_risk_assessment": "Concise 2-3 sentence explanation of the hazard, potential patient impact, and regulatory context"
}
"""


def risk_assessor_node(state: ComplaintGraphState) -> Dict[str, Any]:
    """Assesses complaint risk, severity, priority, and containment action."""
    extracted = state.get("extracted_data", {})
    description = state.get("synthesized_description", "")
    raw_text = state.get("raw_text", "")

    client = Groq(api_key=settings.groq_api_key)
    model = settings.groq_model_risk

    prompt = (
        f"Complaint Information for Risk Analysis:\n"
        f"- Product: {extracted.get('product_name')} ({extracted.get('product_strength_grade')})\n"
        f"- Category: {extracted.get('complaint_category')}\n"
        f"- Batch/Lot: {extracted.get('batch_lot_number')}\n"
        f"- Quantity: {extracted.get('affected_quantity')}\n"
        f"- Formal Description: {description}\n"
        f"- Original Intake Text: {raw_text}\n\n"
        f"Provide the ICH Q9/Q10 risk assessment JSON:"
    )

    assessment: Dict[str, Any] = {}
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": RISK_ASSESSMENT_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=600,
        )
        content = response.choices[0].message.content.strip()
        assessment = json.loads(content)
    except Exception as e:
        logger.error(f"Risk assessment LLM call failed: {e}")
        # Deterministic fallback based on category
        cat = (extracted.get("complaint_category") or "").lower()
        if any(term in cat for term in ["sterility", "foreign matter", "mix-up", "contamination"]):
            assessment = {
                "severity_suggested": SeverityLevel.critical.value,
                "priority": PriorityLevel.high.value,
                "suggested_next_action": "Immediately quarantine retained batch samples and initiate critical deviation.",
                "initial_risk_assessment": "Defect presents potential contamination or sterility assurance hazard requiring immediate containment.",
            }
        elif any(term in cat for term in ["discoloration", "potency", "efficacy", "dissolution"]):
            assessment = {
                "severity_suggested": SeverityLevel.major.value,
                "priority": PriorityLevel.medium.value,
                "suggested_next_action": "Quarantine retained samples for visual and analytical re-assay; retrieve complaint sample from field.",
                "initial_risk_assessment": "Observed physical or chemical change indicates possible batch degradation or stability failure.",
            }
        else:
            assessment = {
                "severity_suggested": SeverityLevel.minor.value,
                "priority": PriorityLevel.low.value,
                "suggested_next_action": "Log complaint for QA trend analysis and review packaging supplier COA.",
                "initial_risk_assessment": "Defect is cosmetic or secondary with minimal direct clinical patient risk.",
            }

    # Normalize severity & priority to valid enum values
    sev = assessment.get("severity_suggested", "Major")
    if sev not in [s.value for s in SeverityLevel]:
        sev = "Major"

    pri = assessment.get("priority", "Medium")
    if pri not in [p.value for p in PriorityLevel]:
        pri = "Medium"

    assessment["severity_suggested"] = sev
    assessment["priority"] = pri

    # Compile the final complaint record combining all nodes
    final_complaint = {
        **extracted,
        "complaint_description": description,
        "severity_suggested": sev,
        "severity_final": sev,  # Default to suggested until confirmed
        "priority": pri,
        "suggested_next_action": assessment.get("suggested_next_action"),
        "initial_risk_assessment": assessment.get("initial_risk_assessment"),
        "status": "ready_to_commit" if state.get("is_valid", True) else "pending_triage",
        "raw_source_text": raw_text,
    }

    return {
        "risk_assessment": assessment,
        "final_complaint": final_complaint,
        "step": "risk_assessor",
        "progress": 100,
        "status_message": f"Assessment complete: Severity '{sev}', Priority '{pri}'. Ready for QMS ledger commit.",
    }
