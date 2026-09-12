from __future__ import annotations

import asyncio
import json
from datetime import datetime

from src.agents.pipeline.state import PipelineState, SourceRef
from src.connectors.base import Source
from src.connectors.registry import resolve_connector
from src.models.connection import Connection
from src.models.pipeline_audit import PipelineRawMessage


def _persist_raw_items(
    db, run_id: int, connection_id: int, provider: str, source_id: str, raw_items: list[dict]
) -> None:
    """Ghi audit CP0 — mỗi item thô 1 dòng, gắn id ngược lên dict để normalize dùng."""
    for raw in raw_items:
        row = PipelineRawMessage(
            run_id=run_id,
            connection_id=connection_id,
            provider=provider,
            source_id=source_id,
            external_id=str(raw.get("id", "")),
            raw_json=json.dumps(raw, ensure_ascii=False),
        )
        db.add(row)
        db.flush()
        raw["_pipeline_raw_message_id"] = row.id
    db.commit()


async def _fetch_one(
    db,
    run_id: int,
    ref: SourceRef,
    time_from: datetime,
    time_to: datetime,
    user_id: str,
    publish_progress=None,
) -> dict:
    connection = db.get(Connection, ref["connection_id"])
    if connection is None or connection.user_id != user_id:
        raise ValueError(f"Không tìm thấy connection {ref['connection_id']} của user.")
    connector_cls, native_source_id = resolve_connector(connection.provider, ref["source_id"])

    connector = connector_cls(connection, db)
    source = Source(id=native_source_id, name=native_source_id)

    on_item = None
    if publish_progress is not None:
        # Đóng riêng 1 bộ đếm cho từng nguồn — 2 nguồn chạy song song
        # (asyncio.gather) không lẫn count của nhau.
        counter = {"count": 0}

        def on_item(_raw_item: dict, label: str) -> None:  # noqa: B023 - counter đóng riêng mỗi lần gọi _fetch_one
            counter["count"] += 1
            publish_progress(ref["source_id"], counter["count"], label)

    raw_items = await connector.fetch_range(source, time_from, time_to, on_item=on_item)
    _persist_raw_items(db, run_id, ref["connection_id"], connection.provider, ref["source_id"], raw_items)
    return {
        "connection_id": ref["connection_id"],
        "connector": connector,
        "source": source,
        "raw_items": raw_items,
    }


async def fetch_node(state: PipelineState) -> dict:
    """Gọi connector song song nhiều nguồn — 1 nguồn lỗi không sập cả batch."""
    db = state["db"]
    run_id = state["run_id"]
    sources = state.get("sources", [])
    publish_progress = state.get("publish_progress")
    results = await asyncio.gather(
        *(
            _fetch_one(db, run_id, ref, state["time_from"], state["time_to"], state["user_id"], publish_progress)
            for ref in sources
        ),
        return_exceptions=True,
    )

    raw_messages: list[dict] = []
    errors = list(state.get("errors", []))
    for ref, result in zip(sources, results):
        if isinstance(result, Exception):
            errors.append(f"fetch {ref['source_id']}: {result}")
            continue
        raw_messages.append(result)

    return {"raw_messages": raw_messages, "errors": errors}
