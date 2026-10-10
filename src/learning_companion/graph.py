from collections.abc import Callable
from typing import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph

from learning_companion.chain import REVIEW_RULES, select_route

MAX_REVISIONS = 1

# Development-only ANSI colours so reviewer and improver logs stand out in the terminal.
RESET = "\033[0m"
DETAIL_COLORS = {"reviewer": "\033[1;38;5;213m", "improver": "\033[1;92m"}


class GraphState(TypedDict):
    user_message: str  # latest question; the router strips a leading /study marker
    messages: list[BaseMessage]  # earlier messages from this request (read-only)
    route: str  # "general" or "study"; empty until the router runs
    draft_answer: str  # current unapproved reply; answer nodes write it, improver replaces it
    review_decision: str  # "approve" or "improve"; empty before the first review
    review_reason: str  # one short sentence from the reviewer
    revision_count: int  # improver rewrites so far; 0 or 1
    final_answer: str  # approved reply; empty until the reviewer approves or accepts


def build_graph(
    general_chain,
    study_chain,
    reviewer_chain,
    improver_chain,
    trace: Callable[[str], None] | None = None,
):
    """Route, draft, review once, improve at most once, review again, end. Chains are passed in."""

    def say(line: str) -> None:
        if trace:
            trace(f"graph: {line}")

    def detail(title: str, data: dict) -> None:
        """Development only: full node inputs/outputs. Never includes the API key."""
        if trace:
            body = "\n".join(f"  {k}: {v}" for k, v in data.items())
            color = DETAIL_COLORS.get(title.split()[0], "")
            bar = "=" * 8
            block = f"{bar} graph[detail] {title.upper()} {bar}\n{body}\n{bar}{bar}"
            trace(f"{color}{block}{RESET}" if color else block)

    def router(state: GraphState) -> dict:
        route, question = select_route(state["user_message"])
        say(f"router -> {route}")
        detail("router", {"input": state["user_message"], "route": route, "question": question})
        return {"route": route, "user_message": question}

    def make_answer_node(name: str, chain):
        def node(state: GraphState) -> dict:
            text = chain.invoke({"history": state["messages"], "question": state["user_message"]})
            say(f"{name} -> draft {len(text)} chars")
            detail(
                name,
                {
                    "history_messages": len(state["messages"]),
                    "question": state["user_message"],
                    "draft": text,
                },
            )
            return {"draft_answer": text}

        return node

    def reviewer(state: GraphState) -> dict:
        count = state["revision_count"]
        draft = state["draft_answer"]
        if count >= MAX_REVISIONS:
            decision, reason = "approve", "revision limit reached"
            detail("reviewer (no model call)", {"revision_count": count, "draft": draft})
        else:
            try:
                review = reviewer_chain.invoke(
                    {"rule": REVIEW_RULES[state["route"]], "draft": draft}
                )
                detail(
                    "reviewer",
                    {
                        "revision_count": count,
                        "rule": REVIEW_RULES[state["route"]],
                        "draft": draft,
                        "raw_review": review,
                    },
                )
                decision, reason = review.decision, " ".join(review.reason.split())
                if decision not in ("approve", "improve"):
                    raise ValueError("unusable decision")
            except Exception as exc:  # noqa: BLE001
                decision, reason = "approve", "review unavailable"
                detail("reviewer error", {"error": repr(exc)})
        say(f"reviewer -> {decision} (revision {count}): {reason[:120]}")
        detail(
            "reviewer verdict",
            {"decision": decision, "reason": reason, "final": decision == "approve"},
        )
        update = {"review_decision": decision, "review_reason": reason}
        if decision == "approve":
            update["final_answer"] = draft
        return update

    def improver(state: GraphState) -> dict:
        text = improver_chain.invoke(
            {
                "rule": REVIEW_RULES[state["route"]],
                "draft": state["draft_answer"],
                "reason": state["review_reason"],
            }
        )
        count = state["revision_count"] + 1
        say(f"improver -> revision {count}")
        detail(
            "improver",
            {
                "reason_given": state["review_reason"],
                "draft_before": state["draft_answer"],
                "draft_after": text,
                "revision_count": count,
            },
        )
        return {"draft_answer": text, "revision_count": count}

    def pick_route(state: GraphState) -> str:
        return state["route"]

    def pick_review(state: GraphState) -> str:
        return state["review_decision"]

    graph = StateGraph(GraphState)
    graph.add_node("router", router)
    graph.add_node("general_chat", make_answer_node("general_chat", general_chain))
    graph.add_node("study_helper", make_answer_node("study_helper", study_chain))
    graph.add_node("reviewer", reviewer)
    graph.add_node("improver", improver)
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router", pick_route, {"general": "general_chat", "study": "study_helper"}
    )
    graph.add_edge("general_chat", "reviewer")
    graph.add_edge("study_helper", "reviewer")
    graph.add_conditional_edges("reviewer", pick_review, {"approve": END, "improve": "improver"})
    graph.add_edge("improver", "reviewer")
    return graph.compile()
