from __future__ import annotations

from src.agents.pipeline.state import PipelineState
from src.models.pipeline_audit import PipelineNormalizedMessage


def normalize_node(state: PipelineState) -> dict:
    db = state["db"]
    run_id = state["run_id"]
    normalized: list[dict] = []
    errors = list(state.get("errors", []))

    for batch in state.get("raw_messages", []):
        connector = batch["connector"]
        source = batch["source"]
        for raw in batch["raw_items"]:
            try:
                item = connector.normalize(raw, source)
            except Exception as exc:  # noqa: BLE001 - 1 message lỗi không được sập cả batch
                errors.append(f"normalize message lỗi: {exc}")
                continue
            item["connection_id"] = batch["connection_id"]

            row = PipelineNormalizedMessage(
                run_id=run_id,
                raw_message_id=raw.get("_pipeline_raw_message_id"),
                provider=item["provider"],
                source_id=item["source_id"],
                external_id=str(item["id"]),
                thread_id=item.get("thread_id"),
                author_id=item.get("author_id"),
                author_name=item.get("author_name"),
                is_self=item.get("is_self", False),
                is_dm=item.get("is_dm", False),
                text=item.get("text", ""),
                sent_at=item["sent_at"],
                deep_link=item.get("deep_link"),
            )
            db.add(row)
            db.flush()
            item["_pipeline_normalized_message_id"] = row.id

            normalized.append(item)

    db.commit()
    return {"normalized": normalized, "errors": errors}
