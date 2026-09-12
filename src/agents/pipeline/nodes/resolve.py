from __future__ import annotations

from src.agents.pipeline.action_understanding import infer_action_hint
from src.agents.pipeline.identity_resolve import resolve_assignee
from src.agents.pipeline.state import PipelineState
from src.agents.pipeline.time_resolve import resolve_due_at
from src.models.pipeline_audit import PipelineResolvedItem


def resolve_node(state: PipelineState) -> dict:
    db = state["db"]
    run_id = state["run_id"]
    user_email = state.get("user_email")
    resolved = []

    for item in state.get("extracted", []):
        hint = infer_action_hint(item.get("evidence_quote") or item.get("message", {}).get("text", ""))
        action_type = item.get("action_type") or hint["action_type"]
        requires_user_action = item.get("requires_user_action", hint["requires_user_action"])
        condition = item.get("condition") or hint["condition"]
        status = item.get("status") or hint["status"]
        certainty = item.get("certainty") or hint["certainty"]
        if "structured_due_at" in item:
            # Jira (rule-based) — due_date đã chuẩn hoá sẵn ở Normalization,
            # không đoán lại từ câu chữ như nhánh LLM. Jira duedate chỉ có
            # ngày, không có giờ -> all_day=True.
            due_at = item["structured_due_at"]
            all_day = True
            ambiguous = False
        else:
            time_expression = item.get("time_expression", "")
            due_at = resolve_due_at(time_expression)
            all_day = False
            ambiguous = due_at is None and bool(time_expression)

        if "structured_assignee" in item:
            assignee = item["structured_assignee"]
            assignee_ambiguous = item.get("structured_assignee_ambiguous", assignee is None)
        else:
            assignee, assignee_ambiguous = resolve_assignee(
                item.get("assignee_hint", ""), item.get("message", {}), user_email
            )

        row = PipelineResolvedItem(
            run_id=run_id,
            extracted_item_id=item.get("_pipeline_extracted_item_id"),
            due_at=due_at,
            all_day=all_day,
            ambiguous=ambiguous,
            assignee=assignee,
            assignee_ambiguous=assignee_ambiguous,
        )
        db.add(row)
        db.flush()

        resolved.append(
            {
                **item,
                "due_at": due_at,
                "all_day": all_day,
                "ambiguous": ambiguous,
                "assignee": assignee,
                "assignee_ambiguous": assignee_ambiguous,
                "action_type": action_type,
                "requires_user_action": requires_user_action,
                "condition": condition,
                "status": status,
                "certainty": certainty,
                "_pipeline_resolved_item_id": row.id,
            }
        )

    db.commit()
    return {"resolved": resolved}
