"""Router node: inspects input payload and determines pipeline path."""
from typing import Dict, Any
from app.agents.state import ComplaintGraphState


def router_node(state: ComplaintGraphState) -> Dict[str, Any]:
    """
    Classifies the input source.
    In Phase 3: routes direct text intake.
    In Phase 4: routes file paths to document loader.
    """
    file_path = state.get("file_path")
    raw_text = state.get("raw_text", "").strip()

    if file_path:
        from pathlib import Path
        filename = Path(file_path).name
        input_type = "file"
        msg = f"Detected document upload: '{filename}'. Routing to Document Loader."
        progress = 10
    else:
        input_type = "text"
        msg = f"Routing text intake ({len(raw_text)} characters) to Entity Extractor."
        progress = 15

    return {
        "input_type": input_type,
        "step": "router",
        "progress": progress,
        "status_message": msg,
    }
