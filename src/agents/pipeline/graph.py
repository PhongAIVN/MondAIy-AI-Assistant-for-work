from langgraph.graph import END, StateGraph

from src.agents.pipeline.nodes.attachment_extract import attachment_extract_node
from src.agents.pipeline.nodes.cluster import cluster_node
from src.agents.pipeline.nodes.evidence import evidence_node
from src.agents.pipeline.nodes.extract_batch import extract_batch_node
from src.agents.pipeline.nodes.fetch import fetch_node
from src.agents.pipeline.nodes.filter import filter_node
from src.agents.pipeline.nodes.make_batches import make_batches_node
from src.agents.pipeline.nodes.normalize import normalize_node
from src.agents.pipeline.nodes.persist import persist_node
from src.agents.pipeline.nodes.reduce import reduce_node
from src.agents.pipeline.nodes.resolve import resolve_node
from src.agents.pipeline.nodes.summary import summary_node
from src.agents.pipeline.nodes.verify import verify_node
from src.agents.pipeline.routing import route_after_filter
from src.agents.pipeline.state import PipelineState


def build_pipeline_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("fetch", fetch_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("filter", filter_node)
    graph.add_node("evidence", evidence_node)
    graph.add_node("attachment_extract", attachment_extract_node)
    graph.add_node("make_batches", make_batches_node)
    graph.add_node("extract_batch", extract_batch_node)
    graph.add_node("verify", verify_node)
    graph.add_node("resolve", resolve_node)
    graph.add_node("cluster", cluster_node)
    graph.add_node("reduce", reduce_node)
    graph.add_node("persist", persist_node)
    graph.add_node("summary", summary_node)

    graph.set_entry_point("fetch")
    graph.add_edge("fetch", "normalize")
    graph.add_edge("normalize", "filter")
    # Cả 2 nhánh đều đi qua evidence + attachment_extract: yêu cầu "tóm tắt
    # mail" cũng cần nội dung file đính kèm y hệt nhánh trích task, trước đây
    # nhánh summary nhảy thẳng tới summary_node nên attachment_text không bao
    # giờ tồn tại cho brief đọc. Rẽ nhánh lùi xuống sau attachment_extract để
    # summary vẫn KHÔNG chạm make_batches/extract_batch/persist (không gọi LLM
    # trích task, không tạo task ngầm — đúng nguyên tắc cũ của route).
    graph.add_edge("filter", "evidence")
    graph.add_edge("evidence", "attachment_extract")
    graph.add_conditional_edges(
        "attachment_extract",
        route_after_filter,
        {"summary": "summary", "task_extraction": "make_batches"},
    )
    graph.add_edge("summary", END)
    graph.add_edge("make_batches", "extract_batch")
    graph.add_edge("extract_batch", "verify")
    graph.add_edge("verify", "resolve")
    graph.add_edge("resolve", "cluster")
    graph.add_edge("cluster", "reduce")
    graph.add_edge("reduce", "persist")
    graph.add_edge("persist", END)

    return graph.compile()


pipeline = build_pipeline_graph()
