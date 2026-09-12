from __future__ import annotations

from src.agents.pipeline.state import PipelineState


def summary_node(state: PipelineState) -> dict:
    """Terminal marker for evidence-only Gmail summaries.

    Brief generation happens after the graph and owns the final LLM call.
    Keeping this node deterministic makes the graph auditable and prevents a
    summary request from silently creating tasks.
    """
    return {"tasks_persisted": [], "summary_items": state.get("filtered", [])}
