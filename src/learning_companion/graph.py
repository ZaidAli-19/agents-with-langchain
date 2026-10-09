from collections.abc import Callable
from typing import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph

from learning_companion.chain import select_route


class GraphState(TypedDict):
    user_message: str  # latest question; the router strips a leading /study marker
    messages: list[BaseMessage]  # earlier messages from this request (read-only)
    route: str  # "general" or "study"; empty until the router runs
    answer: str  # final reply; empty until an answer node runs


def build_graph(general_chain, study_chain, trace: Callable[[str], None] | None = None):
    """START -> router -> (general_chat | study_helper) -> END. Chains are passed in."""

    def say(line: str) -> None:
        if trace:
            trace(f"graph: {line}")

    def router(state: GraphState) -> dict:
        route, question = select_route(state["user_message"])
        say(f"router -> {route}")
        return {"route": route, "user_message": question}

    def make_answer_node(name: str, chain):
        def node(state: GraphState) -> dict:
            text = chain.invoke({"history": state["messages"], "question": state["user_message"]})
            say(f"{name} -> answer {len(text)} chars")
            return {"answer": text}

        return node

    def pick_route(state: GraphState) -> str:
        return state["route"]

    graph = StateGraph(GraphState)
    graph.add_node("router", router)
    graph.add_node("general_chat", make_answer_node("general_chat", general_chain))
    graph.add_node("study_helper", make_answer_node("study_helper", study_chain))
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router", pick_route, {"general": "general_chat", "study": "study_helper"}
    )
    graph.add_edge("general_chat", END)
    graph.add_edge("study_helper", END)
    return graph.compile()
