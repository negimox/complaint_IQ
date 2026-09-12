"""Risk Assessor node: evaluates severity, priority, and containment actions using Groq LLM."""
import json
import logging
from typing import Dict, Any, Optional
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
  "initial_risk_assessment": "Concise 2-3 sentence explanation of the hazard, potential patient impact, and regulatory context",
  "capa_recommendation": "CAPA Type and 2-3 specific ICH Q10 recommended actions (e.g. CAPA Type: OOS Investigation + Process CAPA\\nRecommended Actions:\\n  • Quarantine retained samples for assay\\n  • Initiate OOS investigation per ICH Q10)"
}
"""


def _generate_complaint_summary(client: Groq, model: str, extracted: Dict[str, Any], description: str) -> str:
    """Generates a ≤25-word complaint summary for list/dashboard views."""
    prompt = (
        f"Write a ≤25-word factual summary of this pharmaceutical complaint for a QMS dashboard list view.\n"
        f"Product: {extracted.get('product_name')} ({extracted.get('product_strength_grade')})\n"
        f"Batch: {extracted.get('batch_lot_number')}\n"
        f"Category: {extracted.get('complaint_category')}\n"
        f"Description: {description[:300]}\n\n"
        f"Return only the summary sentence. No labels, no JSON, no quotes."
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise pharmaceutical QMS record summarizer. Output only the summary sentence."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=60,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning(f"Complaint summary generation failed: {e}")
        cat = extracted.get("complaint_category") or "Defect"
        prod = extracted.get("product_name") or "product"
        lot = extracted.get("batch_lot_number") or "N/A"
        return f"{cat} complaint for {prod} (Lot: {lot})."


def _generate_capa_recommendation(extracted: Dict[str, Any], severity: str, llm_capa: Optional[str] = None) -> str:
    """
    Returns structured CAPA recommendation per ICH Q10 guidelines.
    Uses LLM assessment if provided, or applies the authoritative ICH Q10 rubric.
    """
    if llm_capa and isinstance(llm_capa, str) and len(llm_capa.strip()) > 15:
        return llm_capa.strip()

    cat = (extracted.get("complaint_category") or "").lower()
    if severity == "Critical" or any(t in cat for t in ["sterility", "foreign", "contamination", "mix-up"]):
        return (
            "CAPA Type: Batch Recall Evaluation + Immediate Process CAPA\n"
            "Recommended Actions:\n"
            "  • Issue quality hold on remaining batch inventory\n"
            "  • Initiate batch recall assessment per 21 CFR 314.81\n"
            "  • Open critical deviation and notify QA Director & Regulatory Affairs"
        )
    elif any(t in cat for t in ["packaging", "seal", "blister", "foil", "leak"]):
        return (
            "CAPA Type: Packaging Line Inspection + Supplier Audit CAPA\n"
            "Recommended Actions:\n"
            "  • Inspect primary packaging line tooling and seal integrity records\n"
            "  • Audit packaging material supplier Certificate of Analysis (CoA)\n"
            "  • Issue Supplier Corrective Action Request (SCAR)"
        )
    elif any(t in cat for t in ["label", "mislabel", "print"]):
        return (
            "CAPA Type: Label Revision + Label Reconciliation CAPA\n"
            "Recommended Actions:\n"
            "  • Quarantine affected stock and check warehouse inventory\n"
            "  • Perform line clearance and label reconciliation audit\n"
            "  • Retrain packaging operators on verification SOPs"
        )
    elif severity == "Major" or any(t in cat for t in ["discoloration", "potency", "dissolution", "subpotency", "particulate"]):
        return (
            "CAPA Type: OOS Investigation + Supplier/Process CAPA\n"
            "Recommended Actions:\n"
            "  • Quarantine retained samples for analytical re-assay\n"
            "  • Retrieve complaint sample from field for visual inspection\n"
            "  • Initiate Out-Of-Specification (OOS) investigation per ICH Q10"
        )
    else:
        return (
            "CAPA Type: Trend Monitoring — No Immediate CAPA\n"
            "Recommended Actions:\n"
            "  • Log complaint in trending database\n"
            "  • Review at next monthly QA review meeting\n"
            "  • Escalate to CAPA only if 3+ similar occurrences within 6 months"
        )


def risk_assessor_node(state: ComplaintGraphState) -> Dict[str, Any]:
    """Assesses complaint risk, severity, priority, containment action, summary, and CAPA recommendation."""
    extracted = state.get("extracted_data", {})
    description = state.get("synthesized_description", "")
    raw_text = state.get("raw_text", "")

    client = Groq(api_key=settings.groq_api_key)
    model_risk = settings.groq_model_risk
    model_fast = settings.groq_model_extract

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
            model=model_risk,
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
        elif any(term in cat for term in ["discoloration", "potency", "efficacy", "dissolution", "subpotency"]):
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

    # ── Phase 6: Generate complaint summary and CAPA recommendation ────────────
    complaint_summary = _generate_complaint_summary(client, model_fast, extracted, description)
    capa_recommendation = _generate_capa_recommendation(extracted, sev, assessment.get("capa_recommendation"))

    # Compile the final complaint record combining all nodes
    final_complaint = {
        **extracted,
        "complaint_description": description,
        "severity_suggested": sev,
        "severity_final": sev,  # Default to suggested until confirmed
        "priority": pri,
        "suggested_next_action": assessment.get("suggested_next_action"),
        "initial_risk_assessment": assessment.get("initial_risk_assessment"),
        "complaint_summary": complaint_summary,
        "capa_recommendation": capa_recommendation,
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
