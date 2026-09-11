"""Description Synthesizer node: synthesizes formal QMS complaint narrative using Groq LLM."""
import logging
from typing import Dict, Any
from groq import Groq
from app.core.config import settings
from app.agents.state import ComplaintGraphState

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """You are an expert Pharmaceutical Quality Assurance professional drafting a formal Quality Management System (QMS) complaint record under 21 CFR 211.198 and ICH Q10 guidelines.

Your task is to transform informal, raw customer complaint communications into a concise, formal, objective, regulatory-ready complaint description paragraph.

Guidelines:
1. Maintain strict factual objectivity: include who reported the issue, the exact product and batch/lot identifier, packaging condition, affected quantity, and specific physical/clinical defect observed.
2. Avoid emotional, promotional, or speculative language. State observations clearly (e.g., "The customer reported visual discoloration in 12 capsules...").
3. Keep the output as a coherent, single or two-paragraph narrative (between 60 to 150 words).
4. Return ONLY the synthesized text directly. Do not wrap in JSON, Markdown backticks, or prefix with "Here is the summary:".
"""


def description_synthesizer_node(state: ComplaintGraphState) -> Dict[str, Any]:
    """Generates a formal QMS description from raw text and extracted entities."""
    raw_text = state.get("raw_text", "")
    extracted = state.get("extracted_data", {})

    client = Groq(api_key=settings.groq_api_key)
    model = settings.groq_model_extract

    prompt = (
        f"Raw complaint submission:\n{raw_text}\n\n"
        f"Key extracted attributes:\n"
        f"- Reporter: {extracted.get('customer_name', 'N/A')}\n"
        f"- Product: {extracted.get('product_name', 'N/A')} ({extracted.get('product_strength_grade', 'N/A')})\n"
        f"- Batch/Lot: {extracted.get('batch_lot_number', 'N/A')}\n"
        f"- Category: {extracted.get('complaint_category', 'N/A')}\n"
        f"- Quantity: {extracted.get('affected_quantity', 'N/A')}\n\n"
        f"Draft the formal QMS complaint narrative:"
    )

    synthesized_text = ""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1000,
        )
        msg = response.choices[0].message
        synthesized_text = (msg.content or "").strip()
    except Exception as e:
        logger.error(f"Failed to synthesize description: {e}")

    if not synthesized_text:
        cust = extracted.get("customer_name") or "Customer"
        prod = extracted.get("product_name") or "Product"
        dose = extracted.get("product_strength_grade") or ""
        lot = extracted.get("batch_lot_number") or "N/A"
        qty = extracted.get("affected_quantity") or "affected units"
        cat = extracted.get("complaint_category") or "Defect"
        synthesized_text = (
            f"Formal notification received from {cust} concerning {prod} {dose} (Batch/Lot: {lot}). "
            f"The complaint was categorized under '{cat}', involving {qty}. "
            f"The complaint has been registered in the QMS ledger under 21 CFR 211.198 and ICH Q10 guidelines for full investigation."
        )

    return {
        "synthesized_description": synthesized_text,
        "step": "description_synthesizer",
        "progress": 75,
        "status_message": "Synthesized regulatory QMS complaint narrative.",
    }
