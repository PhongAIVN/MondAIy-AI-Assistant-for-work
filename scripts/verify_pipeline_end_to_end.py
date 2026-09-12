"""Chạy thử pipeline THẬT end-to-end (evidence -> extract -> verify -> resolve
-> cluster -> reduce -> persist) với mock_llm=True, dùng chính fixture Outlook
trong golden dataset, rồi serialize qua đúng hàm API frontend dùng
(_to_response trong src/api/tasks.py) để xác nhận Task tạo ra hiển thị đúng
trên UI hiện có. Script kiểm tra thủ công 1 lần, không phải test suite."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

os.environ["MOCK_LLM"] = "true"
sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from src.agents.pipeline.nodes.cluster import cluster_node  # noqa: E402
from src.agents.pipeline.nodes.evidence import evidence_node  # noqa: E402
from src.agents.pipeline.nodes.extract_batch import extract_batch_node  # noqa: E402
from src.agents.pipeline.nodes.filter import filter_node  # noqa: E402
from src.agents.pipeline.nodes.make_batches import make_batches_node  # noqa: E402
from src.agents.pipeline.nodes.persist import persist_node  # noqa: E402
from src.agents.pipeline.nodes.reduce import reduce_node  # noqa: E402
from src.agents.pipeline.nodes.resolve import resolve_node  # noqa: E402
from src.agents.pipeline.nodes.verify import verify_node  # noqa: E402
from src.api.tasks import _to_response  # noqa: E402
from src.connectors.base import Source  # noqa: E402
from src.connectors.outlook import OutlookConnector  # noqa: E402
from src.db import Base  # noqa: E402
from src.models.connection import Connection  # noqa: E402
from src.models.run import Run  # noqa: E402
from src.models.task import Task  # noqa: E402

_DATASET_DIR = Path(__file__).resolve().parents[1] / "eval" / "outlook"
_SOURCE = Source(id="inbox", name="Hộp thư chính")
_USER_EMAIL = "student@example.edu"


def _load_accepted_case() -> dict:
    cases = json.loads((_DATASET_DIR / "cases.json").read_text(encoding="utf-8"))
    for case in cases:
        if case["expected"].get("filter", {}).get("status") == "accepted":
            return case
    raise RuntimeError("Không tìm thấy case accepted trong eval/outlook/cases.json")


def main() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    run = Run(
        user_id=1,
        sources=[],
        range_from=datetime.now(UTC),
        range_to=datetime.now(UTC),
        idempotency_key=f"verify-e2e-{uuid.uuid4()}",
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    case = _load_accepted_case()
    print(f"Dùng golden case: {case['id']} — {case['description']}")

    connection = Connection(provider_user_id=_USER_EMAIL)
    connector = OutlookConnector(connection, db=None)
    normalized_item = connector.normalize(case["input"]["raw_item"], _SOURCE)
    normalized_item["connection_id"] = None

    state: dict = {
        "db": db,
        "run_id": run.id,
        "user_id": str(_USER_EMAIL),
        "user_email": _USER_EMAIL,
        "timezone": "Asia/Ho_Chi_Minh",
        "normalized": [normalized_item],
        "errors": [],
    }

    print("[1/8] filter_node ...")
    state.update(filter_node(state))
    assert state["filtered"], "filter_node loại mất item — case golden phải accepted"
    print(f"      -> {len(state['filtered'])} item filtered, importance={state['filtered'][0].get('importance_score')}")

    print("[2/8] evidence_node ...")
    state.update(evidence_node(state))
    print(f"      -> evidence_text: {state['filtered'][0]['evidence_text'][:80]!r}")

    print("[3/8] make_batches_node ...")
    state.update(make_batches_node(state))
    print(f"      -> {len(state['batches'])} batch")

    print("[4/8] extract_batch_node (mock_llm) ...")
    import asyncio

    state.update(asyncio.run(extract_batch_node(state)))
    assert state["extracted"], "extract_batch_node không sinh item nào"
    print(f"      -> {len(state['extracted'])} extracted, title={state['extracted'][0].get('title')!r}")

    print("[5/8] verify_node ...")
    state.update(verify_node(state))
    print(f"      -> verification_stats={state['verification_stats']}")

    print("[6/8] resolve_node ...")
    state.update(resolve_node(state))
    print(f"      -> due_at={state['resolved'][0].get('due_at')}, assignee={state['resolved'][0].get('assignee')}")

    print("[7/8] cluster_node + reduce_node ...")
    state.update(cluster_node(state))
    state.update(asyncio.run(reduce_node(state)))
    print(f"      -> {len(state['clusters'])} cluster, detail={state['clusters'][0].get('detail')!r}")

    print("[8/8] persist_node ...")
    state.update(persist_node(state))
    task_id = state["tasks_persisted"][0]["task_id"]
    print(f"      -> Task.id={task_id} persisted")

    task_row = db.get(Task, task_id)
    response = _to_response(db, task_row)
    payload = response.model_dump(by_alias=True, mode="json")

    print("\n=== TaskResponse (đúng payload frontend nhận qua GET /api/v1/tasks) ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    assert payload["title"], "title rỗng"
    assert payload["detail"], "detail rỗng — frontend sẽ hiện fallback thay vì tóm tắt thật"
    assert payload["evidence"], "evidence rỗng — không có gì trace về nguồn"
    print("\nOK: Task đi hết pipeline mới (evidence + verify), TaskResponse hợp lệ cho frontend.")


if __name__ == "__main__":
    main()
