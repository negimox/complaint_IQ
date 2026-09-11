"""LangGraph pipeline for ComplaintIQ: orchestrates multi-agent intake, extraction, and triage."""
import asyncio
from typing import AsyncGenerator, Dict, Any
from langgraph.graph import StateGraph, START, END

from app.agents.state import ComplaintGraphState
from app.agents.nodes.router import router_node
from app.agents.nodes.document_loader import document_loader_node
from app.agents.nodes.entity_extractor import entity_extractor_node
from app.agents.nodes.validator import validator_node
from app.agents.nodes.description_synthesizer import description_synthesizer_node
from app.agents.nodes.risk_assessor import risk_assessor_node


def route_intake(state: ComplaintGraphState) -> str:
    """Determines whether to process document file or raw text directly."""
    if state.get("input_type") == "file" or state.get("file_path"):
        return "document_loader"
    return "entity_extractor"


def build_complaint_graph():
    """Constructs the LangGraph state machine for complaint ingestion and triage."""
    workflow = StateGraph(ComplaintGraphState)

    # Register nodes
    workflow.add_node("router", router_node)
    workflow.add_node("document_loader", document_loader_node)
    workflow.add_node("entity_extractor", entity_extractor_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("description_synthesizer", description_synthesizer_node)
    workflow.add_node("risk_assessor", risk_assessor_node)

    # Conditional routing: file vs raw text
    workflow.add_edge(START, "router")
    workflow.add_conditional_edges(
        "router",
        route_intake,
        {
            "document_loader": "document_loader",
            "entity_extractor": "entity_extractor",
        },
    )
    workflow.add_edge("document_loader", "entity_extractor")
    workflow.add_edge("entity_extractor", "validator")
    workflow.add_edge("validator", "description_synthesizer")
    workflow.add_edge("description_synthesizer", "risk_assessor")
    workflow.add_edge("risk_assessor", END)

    return workflow.compile()


complaint_pipeline = build_complaint_graph()


async def stream_complaint_intake(
    raw_text: str,
    complaint_id: str | None = None,
    session_id: str | None = None,
    file_path: str | None = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Executes the LangGraph pipeline asynchronously, yielding progress events at each node
    for Server-Sent Events (SSE) streaming to the frontend.
    """
    initial_state: ComplaintGraphState = {
        "raw_text": raw_text,
        "file_path": file_path,
        "complaint_id": complaint_id,
        "session_id": session_id,
        "step": "init",
        "progress": 5,
        "status_message": "Initializing ComplaintIQ intake pipeline...",
    }

    # Emit initial event
    yield {
        "step": "init",
        "progress": 5,
        "status_message": "Intake pipeline initiated...",
    }

    accumulated_state = dict(initial_state)

    # Use astream to yield updates step by step
    async for output in complaint_pipeline.astream(initial_state):
        for node_name, node_state in output.items():
            accumulated_state.update(node_state)
            yield {
                "step": node_state.get("step", node_name),
                "progress": node_state.get("progress", 50),
                "status_message": node_state.get("status_message", ""),
                "raw_text": accumulated_state.get("raw_text", ""),
                "extracted_data": accumulated_state.get("extracted_data"),
                "validation_errors": accumulated_state.get("validation_errors"),
                "missing_fields": accumulated_state.get("missing_fields"),
                "is_valid": accumulated_state.get("is_valid"),
                "synthesized_description": accumulated_state.get("synthesized_description"),
                "risk_assessment": accumulated_state.get("risk_assessment"),
                "final_complaint": accumulated_state.get("final_complaint"),
            }
