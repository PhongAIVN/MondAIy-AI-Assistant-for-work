import pytest

import src.agents.pipeline.graph as graph_module


@pytest.mark.asyncio
async def test_summary_graph_skips_task_nodes(monkeypatch):
    called = []

    async def fetch(state):
        called.append("fetch")
        return {"raw_messages": [{"id": "raw"}]}

    def normalize(state):
        called.append("normalize")
        return {"normalized": [{"id": "m1"}]}

    def filter_node(state):
        called.append("filter")
        return {"filtered": [{"id": "m1"}]}

    def named(name, result):
        def node(state):
            called.append(name)
            return result

        return node

    monkeypatch.setattr(graph_module, "fetch_node", fetch)
    monkeypatch.setattr(graph_module, "normalize_node", normalize)
    monkeypatch.setattr(graph_module, "filter_node", filter_node)
    monkeypatch.setattr(graph_module, "evidence_node", named("evidence", {"filtered": [{"id": "m1"}]}))
    monkeypatch.setattr(
        graph_module, "attachment_extract_node", named("attachment_extract", {"filtered": [{"id": "m1"}]})
    )
    monkeypatch.setattr(graph_module, "summary_node", named("summary", {"summary_items": [{"id": "m1"}]}))
    monkeypatch.setattr(graph_module, "make_batches_node", named("make_batches", {"batches": []}))
    monkeypatch.setattr(graph_module, "extract_batch_node", named("extract_batch", {"extracted": []}))
    monkeypatch.setattr(graph_module, "resolve_node", named("resolve", {"resolved": []}))
    monkeypatch.setattr(graph_module, "cluster_node", named("cluster", {"clusters": []}))
    monkeypatch.setattr(graph_module, "reduce_node", named("reduce", {"clusters": []}))
    monkeypatch.setattr(graph_module, "persist_node", named("persist", {"tasks_persisted": []}))

    result = await graph_module.build_pipeline_graph().ainvoke({"mode": "summary"})

    assert result["summary_items"] == [{"id": "m1"}]
    # evidence + attachment_extract nay nằm CHUNG cho cả 2 nhánh: tóm tắt mail
    # cũng cần nội dung file đính kèm. Nhánh summary vẫn không được chạm
    # make_batches/extract_batch/resolve/cluster/reduce/persist — không gọi LLM
    # trích task, không tạo task ngầm.
    assert called == ["fetch", "normalize", "filter", "evidence", "attachment_extract", "summary"]


@pytest.mark.asyncio
async def test_task_graph_runs_every_stage_with_mock_nodes(monkeypatch):
    called = []

    def node(name, key, value=None):
        def run(state):
            called.append(name)
            return {key: value if value is not None else state.get(key, [])}

        return run

    monkeypatch.setattr(graph_module, "fetch_node", node("fetch", "raw_messages", []))
    monkeypatch.setattr(graph_module, "normalize_node", node("normalize", "normalized", []))
    monkeypatch.setattr(graph_module, "filter_node", node("filter", "filtered", []))
    monkeypatch.setattr(graph_module, "evidence_node", node("evidence", "filtered", []))
    monkeypatch.setattr(graph_module, "make_batches_node", node("make_batches", "batches", []))
    monkeypatch.setattr(graph_module, "extract_batch_node", node("extract_batch", "extracted", []))
    monkeypatch.setattr(graph_module, "verify_node", node("verify", "extracted", []))
    monkeypatch.setattr(graph_module, "resolve_node", node("resolve", "resolved", []))
    monkeypatch.setattr(graph_module, "cluster_node", node("cluster", "clusters", []))
    monkeypatch.setattr(graph_module, "reduce_node", node("reduce", "clusters", []))
    monkeypatch.setattr(graph_module, "persist_node", node("persist", "tasks_persisted", []))
    monkeypatch.setattr(graph_module, "summary_node", node("summary", "summary_items", []))

    await graph_module.build_pipeline_graph().ainvoke({"mode": "task_extraction"})

    assert called == [
        "fetch",
        "normalize",
        "filter",
        "evidence",
        "make_batches",
        "extract_batch",
        "verify",
        "resolve",
        "cluster",
        "reduce",
        "persist",
    ]
