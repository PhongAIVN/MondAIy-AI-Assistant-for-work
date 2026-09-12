from langgraph.graph import END, StateGraph

from src.agents.nodes.core_nodes import action_node, measure_outcome_node, observe_node, respond_node, think_node
from src.agents.state import AgentState


def should_continue(state: AgentState) -> str:
    """Sau mỗi lượt nghĩ, hoặc chạy action, hoặc tổng hợp câu trả lời."""
    if state.get("error"):
        return "measure"
    if state.get("pending_tool_calls"):
        return "action"
    return "respond"


def should_replan_after_observe(state: AgentState) -> str:
    """Chỉ quay lại think khi batch trước có dependency cần observation mới."""
    metadata = state.get("metadata") or {}
    return "respond" if metadata.get("respond_after_tool_batch") else "think"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Vòng agent tách node để trace thể hiện đúng think → action → observe.
    # `observe` đưa kết quả tool trở lại state, rồi `think` mới quyết định bước
    # kế tiếp; không còn chạy một batch tool rồi nhảy thẳng sang response.
    graph.add_node("think", think_node)
    graph.add_node("action", action_node)
    graph.add_node("observe", observe_node)
    graph.add_node("respond", respond_node)
    graph.add_node("measure", measure_outcome_node)

    graph.set_entry_point("think")
    graph.add_conditional_edges("think", should_continue)
    graph.add_edge("action", "observe")
    graph.add_conditional_edges("observe", should_replan_after_observe)
    graph.add_edge("respond", "measure")
    graph.add_edge("measure", END)

    return graph.compile()


agent = build_graph()
