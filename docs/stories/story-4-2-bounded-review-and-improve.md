# Story 4.2 — Bounded Review and Improve

## Purpose

Extend the Story 4.1 LangGraph with a small quality check. After an answer node writes a draft, a reviewer checks it once against a short fixed rule. If the draft needs work, an improver rewrites it once, the reviewer looks again, and the answer is sent. The cycle is allowed to run once and no more. This finishes the capstone: a Learning Companion Chatbot in Open WebUI, a routed LangGraph workflow, two LangChain answer chains, and one bounded review step.

Project path: the repository root (there is no `docs/config.yaml`).

## What this story implements in plain English

- A question is routed exactly as in Story 4.1. The general-chat or study-helper step now writes a **draft**, not the final reply.
- A **reviewer** reads the draft once. It answers `approve` or `improve`, with one short reason. It judges the draft against a short fixed classroom rule for its route.
- If the reviewer says `approve`, the draft becomes the final answer and the workflow stops.
- If the reviewer says `improve`, an **improver** rewrites the draft **once**, using the reviewer's reason. The reviewer then looks again. This second look cannot send the answer back for more work: it accepts the draft, and the workflow stops.
- So the most that can happen to any question is: one draft, one improvement, then stop. Nothing here keeps trying until it is perfect, plans, or acts on its own.

Terminology used here:

- The reviewer and improver are small LLM-powered specialist nodes. For this classroom example they may be called specialist agents.
- The router stays ordinary Python logic. It is not an agent.
- The workflow has no tools. An MCP tool call could be a future node, but **MCP is not implemented in this story or this course**.

## Prerequisites

- Story 4.1 is complete: `src/learning_companion/graph.py` has `GraphState`, `build_graph()` and the nodes `router`, `general_chat`, `study_helper`, and Open WebUI shows both routes working.
- Stories 1.1–4.1 are complete. The existing chains and `select_route()` in `chain.py` are unchanged.
- The untracked `.env` holds the existing key and model name. The handout says "Grok"; the code and `.env.example` use Gemini through `langchain-google-genai`. Do not change settings or provider.
- Open WebUI already points at `http://127.0.0.1:8000/v1`. Do **not** reinstall, reconfigure, modify, or build it.
- Before editing, read `docs/architecture.md`, Stories 1.1–4.1, `.env.example`, and `src/learning_companion/` (`chain.py`, `graph.py`, `main.py`, `config.py`). Preserve routes, settings, JSON and SSE shapes, history handling, the Story 4.1 routing path, and `tests/test_health.py`.
- Do not install or add dependencies. Everything needed is already installed.

## Work to do

Keep the change small. Add no endpoints, settings, providers, UI, storage, response fields, tools, or Open WebUI plugins.

### 1. The new state, in plain English (read before coding)

Story 4.1 state had `user_message`, `messages`, `route` and `answer`. This story renames `answer` to `draft_answer` and adds four more fields. `user_message`, `messages` and `route` do not change.

| Field | Plain-English meaning | Written by |
| --- | --- | --- |
| `draft_answer` | The current version of the reply, not yet approved. The answer nodes write the first draft and the improver replaces it once. (This replaces 4.1's `answer`.) | answer nodes, improver |
| `review_decision` | The reviewer's verdict on the current draft: `approve` or `improve`. Empty before the first review. | reviewer |
| `review_reason` | One short plain-English sentence explaining the verdict. The improver reads it. | reviewer |
| `revision_count` | How many times the improver has rewritten the draft: starts at `0` and can only reach `1`. This number is what stops the cycle. | improver |
| `final_answer` | The approved reply that is sent to Open WebUI. Empty until the reviewer approves or accepts a draft. | reviewer |

The state holds nothing else: no plans, tool results, scores or stored memory.

### 2. `src/learning_companion/chain.py` (add only)

- Leave the two answer chains, their instructions, `split_conversation()`, `select_route()` and `MAX_HISTORY_MESSAGES` as they are.
- Add `REVIEW_RULES`, a short fixed application-owned rule, one for each route:
  - `general`: friendly, short, plain English; answers what was asked; does not force the study format; does not claim to browse, look things up, or be certainly correct.
  - `study`: has **Explanation** (2–3 short sentences, plain English), **Example**, and exactly one **Next step** that is a statement, not a question; concise; no claim to research or retrieve information.
- Add `build_reviewer_chain(settings)`: a prompt (reviewer instruction + the rule for the route, the draft) → the same configured model with structured output → a small Pydantic model `Review` with `decision: Literal["approve", "improve"]` and `reason: str` (one short sentence). Use LangChain's `with_structured_output`. The reviewer judges only; it must not rewrite the answer. Reuse the same key and model checks and `ConfigurationError` messages as the existing builders.
- Add `build_improver_chain(settings)`: a prompt (improver instruction, the route's rule, the draft, the reviewer's reason) → the same model → `StrOutputParser`. The instruction says: rewrite the draft once to fix the stated problem, keep what is already good, return only the improved answer, and do not add research, tools or new topics.
- Keep both instructions application-owned and never log them.

### 3. `src/learning_companion/graph.py`

Extend `GraphState` and `build_graph()`. Do not rebuild them. Pass the two new chains in as `reviewer_chain` and `improver_chain` (same pattern as the answer chains).

- `router`: unchanged.
- `general_chat` and `study_helper`: unchanged except they write `{"draft_answer": text}` instead of `{"answer": text}`.
- New `reviewer` node:
  - If `revision_count` is `1`: **do not call the model.** Accept the current draft: write `review_decision = "approve"`, a fixed `review_reason` (for example `revision limit reached`), and `final_answer = draft_answer`.
  - Otherwise call `reviewer_chain` with the route and `draft_answer`. Write `review_decision` and `review_reason`. If the decision is `approve`, also write `final_answer = draft_answer`.
  - If the reviewer call fails or returns something unusable, treat it as `approve` with the reason `review unavailable`. Do not retry.
- New `improver` node: call `improver_chain` with the route, `draft_answer` and `review_reason`. Write `{"draft_answer": improved_text, "revision_count": state["revision_count"] + 1}`. It makes no routing choice and uses no tools.
- Edges. Keep every Story 4.1 edge except `general_chat → END` and `study_helper → END`, which are replaced by the ones below:
  - `general_chat → reviewer` and `study_helper → reviewer`
  - conditional from `reviewer`: if `review_decision == "approve"` go to `END`; if `"improve"` go to `improver`. The reviewer only ever writes `improve` while `revision_count` is `0`, so the improver can never run twice.
  - `improver → reviewer`
- Full graph:

  ```
  START → router ──general──→ general_chat ─┐
                 └──study────→ study_helper ─┤
                                             ▼
                       ┌──────────────── reviewer ──approve──→ END
                       │                     ▲
                       └──improve (only when revision_count = 0)
                                ▼            │
                             improver ───────┘
  ```

- No other loop, retry, planner, tool call or extra node.
- Trace lines (development only, no keys, no instruction text, no message text), one per node: `graph: router -> study`, `graph: study_helper -> draft 399 chars`, `graph: reviewer -> improve (revision 0): <reason>`, `graph: improver -> revision 1`, `graph: reviewer -> approve (revision 1): <reason>`. The review reason is a short model-written sentence about the answer's style. Limit it to 120 characters in the trace.

### 4. `src/learning_companion/main.py`

- Build the reviewer and improver chains alongside the existing two, with the same `ConfigurationError` handling, and pass them into `build_graph()`.
- Initial state: add `"draft_answer": ""`, `"review_decision": ""`, `"review_reason": ""`, `"revision_count": 0`, `"final_answer": ""`, and drop `"answer"`.
- Normal replies: use `result["route"]` for the label and `result["final_answer"]` as the text. JSON shape, label and `502` error shape stay the same.
- Streaming replies: keep the SSE chunk shape, the stop chunk and `[DONE]`. **Do not stream draft text.** A draft may still be replaced by the improver, so partial draft text would show Open WebUI an answer that then changes. Instead use `graph.stream(state, stream_mode="updates")`: send the route label as the first content chunk when the router update arrives, and send `final_answer` as content when the reviewer update that contains it arrives. Streaming therefore arrives as the label followed by the whole final answer, not word by word. Say this plainly in the handover. This replaces the Story 4.1 token streaming and the `stream_mode="messages"` code.
- Do not change `/health`, `/v1/models`, request parsing, or error shapes. Add no custom Open WebUI events or fields.

### 5. `docs/architecture.md`

Add a **Bounded review (Story 4.2)** section covering:

- the full graph diagram above;
- the new nodes, `reviewer` and `improver`, and what each does and does not do;
- the five new/changed state fields (`draft_answer` replaces `answer`) in plain English;
- edge rules: answer nodes go to reviewer; approve goes to `END`; improve goes to the improver only while `revision_count` is zero; the improver returns to the reviewer; at `revision_count` one the reviewer accepts the draft and ends;
- the one-revision limit and why streaming now sends the final answer in one piece;
- the trace format;
- the deliberate scope boundary: no tools, MCP, RAG, web search, persistence, human approval, additional agents, or retries beyond the single improvement.

Update the **Routing workflow (Story 4.1)** section so it points to this one for the current graph, and update the **Chain behaviours** table with the reviewer and improver.

### Files this story changes

| File | Change |
| --- | --- |
| `src/learning_companion/chain.py` | add `REVIEW_RULES`, `Review`, `build_reviewer_chain`, `build_improver_chain` |
| `src/learning_companion/graph.py` | extend state; add `reviewer` and `improver` nodes and the bounded edges |
| `src/learning_companion/main.py` | build and pass the two chains; use `final_answer`; stream final answer only |
| `docs/architecture.md` | full graph, new nodes, state, edge rules, scope |

Do not change `config.py`, `.env.example`, `pyproject.toml`, `uv.lock`, `study_dev.py`, `tests/test_health.py`, or Open WebUI. If one seems necessary, stop and say why.

### Out of scope

More than one improvement, retries, a planner, tools, MCP, RAG, web search, human approval, databases or persistence, additional agents, LLM-based routing, scoring dashboards, custom Open WebUI events or response fields, observability platforms, broad test suites, production controls, and deployment.

## Completion checks

Run only these and report the real results:

```
uv run ruff format .
uv run ruff check .
uv run uvicorn learning_companion.main:app --app-dir src --host 127.0.0.1 --port 8000
```

With the server running (`APP_ENV=development`) and the real key in `.env`, use the existing Open WebUI chat. Replies now take longer, because one question can make up to four model calls (draft, review, improve; the second review makes no model call).

1. **Approved directly.** Send `Hi, how are you?`.
   - **Expected in Open WebUI:** a friendly reply starting with `[Route: general]`.
   - **Expected trace:**
     ```
     graph: router -> general
     graph: general_chat -> draft N chars
     graph: reviewer -> approve (revision 0): <short reason>
     ```
2. **Review, improve, review.** Send `/study Explain recursion, closures and decorators`. This is a broad question likely to produce a crowded draft.
   - **Expected in Open WebUI:** a reply starting with `[Route: study]`, with an explanation, an example and one next step, usually tighter than the draft.
   - **Expected trace:**
     ```
     graph: router -> study
     graph: study_helper -> draft N chars
     graph: reviewer -> improve (revision 0): <short reason>
     graph: improver -> revision 1
     graph: reviewer -> approve (revision 1): revision limit reached
     ```
   - The reviewer is an LLM, so it may approve the first draft. If so, try `/study Explain APIs, databases, caching and queues` once. If that is also approved, report the trace you got instead of forcing it. Never edit the rule or the question to make the improver run.
3. **Final answer in Open WebUI.** Both final answers appear in the same conversation through `http://127.0.0.1:8000/v1`. The reply is the label, then the final answer. It never shows a draft that was replaced.
4. **Bound holds.** In no trace does `improver` appear more than once, and `revision` never exceeds 1.
5. **Safe trace.** No trace line contains the API key, instruction text, or the learner's message text.

Do not add a test suite, an evaluation harness or any other check.

## Handover

- List exactly which files changed and which commands were actually run, with outcomes.
- Report what each Open WebUI message showed and paste the compact trace for each. If the improver path did not occur, say so plainly.
- State that streaming now sends the label then the final answer as one piece, and why.
- Confirm the endpoints, settings, provider, history handling, JSON/SSE shapes and Story 4.1 routing are unchanged, no key or instruction text was printed, and `.env` stays untracked.
- **Final capstone outcome:** a Learning Companion Chatbot, used through the supplied Open WebUI, served by one FastAPI OpenAI-compatible endpoint, with ordinary-Python routing, two LangChain answer chains, and a LangGraph workflow that drafts, reviews once, improves at most once, and answers. It has no tools, MCP, retrieval or stored memory. Those can be future nodes or services, and a tool or MCP call could sit inside one.
