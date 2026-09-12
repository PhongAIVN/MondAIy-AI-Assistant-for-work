from __future__ import annotations

from src.agents.pipeline.state import PipelineState
from src.models.pipeline_audit import PipelineBatch, PipelineFilteredMessage

_BATCH_SIZE = 6  # từng là 18 — batch to làm model bị dilution, dễ bỏ sót tín
# hiệu rõ ràng khi phải phán 1 lượt cho nhiều tin không liên quan nhau. Đổi
# nhỏ lại đánh đổi nhiều lượt gọi LLM hơn/lần Sync, nhưng recall cao hơn hẳn.


def make_batches_node(state: PipelineState) -> dict:
    db = state["db"]
    run_id = state["run_id"]
    filtered = state.get("filtered", [])
    batches = [filtered[i : i + _BATCH_SIZE] for i in range(0, len(filtered), _BATCH_SIZE)]

    for index, batch in enumerate(batches):
        row = PipelineBatch(run_id=run_id, batch_index=index, item_count=len(batch))
        db.add(row)
        db.flush()
        for item in batch:
            item["_pipeline_batch_id"] = row.id
            filtered_message_id = item.get("_pipeline_filtered_message_id")
            if filtered_message_id is not None:
                filtered_row = db.get(PipelineFilteredMessage, filtered_message_id)
                if filtered_row is not None:
                    filtered_row.batch_id = row.id
    db.commit()

    return {"batches": batches}
