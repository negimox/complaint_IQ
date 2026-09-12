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

CAPA_PROMPT = """You are a pharmaceutical QA expert trained in ICH Q10 Corrective and Preventive Action (CAPA) methodology.

Based on the complaint category and severity provided, recommend the most appropriate CAPA type and concrete actions.

CAPA RUBRIC (apply strictly):
- Critical / Sterility / Foreign Matter / Contamination → "Batch Recall Evaluation + Immediate Process CAPA"
  Actions: Issue quality hold on remaining batch, initiate batch recall assessment per 21 CFR 314.81, open critical deviation, quarantine all retained samples, notify QA Director and Regulatory Affairs.
- Major / Discoloration / Subpotency / Dissolution → "OOS Investigation + Supplier/Process CAPA"
  Actions: Quarantine retained samples for analytical re-assay, retrieve complaint sample from field, initiate OOS investigation per ICH Q10, inspect manufacturing batch records, review stability data, audit implicated supplier if NPM involved.
- Major / Packaging Defect → "Packaging Line Inspection + Supplier Audit CAPA"
  Actions: Inspect primary packaging line for tooling defects, audit packaging material supplier CoA, check seal integrity testing records, initiate supplier corrective action request (SCAR).
- Major / Labeling Defect → "Label Revision + Label Reconciliation CAPA"
  Actions: Withdraw mislabeled stock, initiate label revision through change control, perform label reconciliation audit, retrain labeling operators.
- Minor / Cosmetic → "Trend Monitoring — No Immediate CAPA"
  Actions: Log complaint in trending database, review at next monthly QA review meeting. Escalate to CAPA only if trend threshold (3+ similar complaints in 6 months) is exceeded.

Return ONLY a valid JSON object:
{
  "capa_type": "short label of CAPA type (e.g. 'OOS Investigation + Supplier Audit CAPA')",
  "recommended_actions": ["action 1", "action 2", "action 3"],
  "rationale": "One sentence explaining why this CAPA type was selected"
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


def _generate_capa_recommendation(client: Groq, model: str, extracted: Dict[str, Any], severity: str) -> str:
    """Generates a structured CAPA recommendation JSON string using the ICH Q10 rubric."""
    prompt = (
        f"Complaint Category: {extracted.get('complaint_category')}\n"
        f"Severity: {severity}\n"
        f"Product: {extracted.get('product_name')} ({extracted.get('product_strength_grade')})\n"
        f"Impacted NPM: {extracted.get('impacted_npm') or 'None stated'}\n\n"
        f"Apply the CAPA rubric and return the JSON recommendation:"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CAPA_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=400,
        )
        content = (resp.choices[0].message.content or "").strip()
        parsed = json.loads(content)
        # Format as readable text for storage
        capa_type = parsed.get("capa_type", "")
        actions = parsed.get("recommended_actions", [])
        rationale = parsed.get("rationale", "")
        lines = [f"CAPA Type: {capa_type}", f"Rationale: {rationale}", "Recommended Actions:"]
        lines += [f"  • {a}" for a in actions]
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"CAPA recommendation generation failed: {e}")
        # Deterministic fallback based on severity
        if severity == "Critical":
            return "CAPA Type: Batch Recall Evaluation + Immediate Process CAPA\nRecommended Actions:\n  • Issue quality hold on remaining batch\n  • Initiate batch recall assessment per 21 CFR 314.81\n  • Open critical deviation and notify QA Director"
        elif severity == "Major":
            return "CAPA Type: OOS Investigation + Supplier/Process CAPA\nRecommended Actions:\n  • Quarantine retained samples for analytical re-assay\n  • Retrieve complaint sample from field\n  • Initiate OOS investigation per ICH Q10"
        else:
            return "CAPA Type: Trend Monitoring — No Immediate CAPA\nRecommended Actions:\n  • Log complaint in trending database\n  • Review at next monthly QA meeting"


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
    capa_recommendation = _generate_capa_recommendation(client, model_fast, extracted, sev)

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
