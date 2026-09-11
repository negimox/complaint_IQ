"""Entity Extractor node: extracts structured QMS complaint entities using Groq LLM."""
import json
import logging
from typing import Dict, Any
from groq import Groq
from app.core.config import settings
from app.agents.state import ComplaintGraphState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior Pharmaceutical Quality Assurance (QA) and QMS specialist.
Your task is to extract structured complaint data from raw intake text into strict JSON adhering to ICH Q10 and 21 CFR 211.198 standards.

Follow these strict rules:
1. Return ONLY a valid JSON object. No Markdown code blocks, no explanation text outside the JSON.
2. Extract fields accurately from the text. DO NOT hallucinate. If a field is truly not present or inferrable, set its value to null.
3. customer_name: If an institution, pharmacy, clinic, hospital, distributor, or individual reported the complaint (e.g., "Apollo Pharmacy", "Metro Health", "John Smith"), extract that exact name as "customer_name".
4. complaint_source: Standardize to one of: "Pharmacy", "Email", "Distributor", "Phone", "Portal", "Customer", "Hospital", or "Other".
5. Standardize dates to ISO format: "YYYY-MM-DD". If only month/year is given (e.g., "Jan 2026"), use the first day of that month (e.g., "2026-01-01"). If complaint_date is not stated in the text, use today's date in YYYY-MM-DD format.
6. affected_quantity: Include quantity with unit and container if stated (e.g. "12 capsules in 1 sealed bottle", "48 capsules", "25 kg HDPE drum").
7. Standardize complaint_category to the most appropriate category: "Discoloration", "Foreign Matter / Contamination", "Packaging Defect", "Labeling Defect", "Subpotency / Efficacy", "Dissolution / Physical", "Adverse Event", "Damaged Goods", or "Other".

Expected JSON Schema:
{
  "complaint_source": string | null,
  "customer_name": string | null,
  "product_name": string | null,
  "product_strength_grade": string | null,
  "batch_lot_number": string | null,
  "manufacturing_date": "YYYY-MM-DD" | null,
  "expiry_date": "YYYY-MM-DD" | null,
  "affected_quantity": string | null,
  "originating_site_block": string | null,
  "impacted_npm": string | null,
  "complaint_category": string | null,
  "complaint_date": "YYYY-MM-DD" | null
}
"""


def entity_extractor_node(state: ComplaintGraphState) -> Dict[str, Any]:
    """Extracts entities from raw intake text using Groq LLM."""
    raw_text = state.get("raw_text", "")
    if not raw_text.strip():
        return {
            "extracted_data": {},
            "step": "entity_extractor",
            "progress": 35,
            "status_message": "No raw text provided for extraction.",
        }

    client = Groq(api_key=settings.groq_api_key)
    model = settings.groq_model_extract

    prompt = f"Extract all pharmaceutical complaint entities from this text:\n\n{raw_text}"

    extracted_dict: Dict[str, Any] = {}
    last_error = None

    # Try up to 2 times for strict JSON parsing
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt if attempt == 0 else f"{prompt}\n\nPlease ensure strictly valid JSON."},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1000,
            )
            content = response.choices[0].message.content.strip()
            # Clean up if markdown code fences are present
            if content.startswith("```"):
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()

            extracted_dict = json.loads(content)
            break
        except Exception as e:
            logger.warning(f"Entity extraction attempt {attempt + 1} failed: {e}")
            last_error = e

    if not extracted_dict and last_error:
        logger.error(f"Failed to extract entities: {last_error}")

    product = extracted_dict.get("product_name") or "product"
    batch = extracted_dict.get("batch_lot_number") or "unspecified batch"

    return {
        "extracted_data": extracted_dict,
        "step": "entity_extractor",
        "progress": 35,
        "status_message": f"Identified entities for {product} (Lot: {batch}).",
    }
