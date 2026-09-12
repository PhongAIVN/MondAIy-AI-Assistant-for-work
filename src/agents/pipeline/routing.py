from __future__ import annotations

from typing import Literal

PipelineRoute = Literal["summary", "task_extraction"]


def route_after_filter(state: dict) -> PipelineRoute:
    """Choose the smallest safe flow once evidence + attachments are ready.

    A user asking for a summary must not incur task extraction, identity
    resolution, clustering, or persistence. It does still need evidence
    selection and attachment extraction, so the branch point sits after those
    two deterministic/bounded nodes rather than immediately after filtering.
    Unknown/missing modes retain the historical task-extraction behavior for
    backwards compatibility.
    """
    return "summary" if state.get("mode") == "summary" else "task_extraction"
