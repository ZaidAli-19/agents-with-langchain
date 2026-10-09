# Story 4.1 — LangGraph Routing Workflow

## Purpose

Replace the plain Python `if/else` route from Story 3.2 with one small LangGraph workflow. The behaviour stays the same: `/study ...` goes to the study helper, everything else goes to general chat. What changes is that the route, the shared state, the steps and the connections between them are now visible in code and in a short trace. Both existing LangChain chains are reused as they are. Story 4.2 adds a bounded review step to this graph.

Project path: the repository root (there is no `docs/config.yaml`).

## What this story implements in plain English

- A question arrives in Open WebUI exactly as before and goes to the same `/v1/chat/completions` endpoint. The app splits it into earlier messages (history) and the latest question, as in Story 2.2.
- The app then starts a small workflow, a **graph**: a set of named steps (**nodes**) joined by arrows (**edges**), plus one shared notepad (**state**) that each step can read and write.
- **Step 1, the router**, reads the question. If it starts with `/study` followed by text, it writes `study` on the notepad and removes the `/study` marker. Otherwise it writes `general`. This is the same plain Python rule as Story 3.2, not an AI decision.
- **Step 2** is one of two answer steps, chosen by that route. The general-chat step or the study-helper step runs the matching existing LangChain chain and writes the final answer on the notepad. Then the workflow ends.
- The final answer goes through the same normal-JSON or streaming code as before, so Open WebUI shows it as usual with the same `[Route: ...]` label. The terminal shows a short trace of which route and which steps ran.

Terminology used here:

- A **node** is a focused piece of work. It is not automatically an agent.
- The **router** is ordinary application logic, not an agent and not an LLM call.
- The two answer nodes call Grok-configured (in this repo: the existing Gemini) chains. They can be called small specialist behaviours: each has its own instructions and one job.
- A tool call, including an MCP tool, could later sit inside a node. **MCP is not implemented in this course story.**

## Prerequisites

- Story 3.2 is complete: `select_route()` in `src/learning_companion/chain.py` and the route-based chain choice in `main.py` work in Open WebUI.
- Stories 1.1–3.1 are complete, so `build_chain(settings)`, `build_study_helper_chain(settings)`, `split_conversation()` and `MAX_HISTORY_MESSAGES` exist.
- The untracked `.env` holds the existing key and model name. The handout says "Grok"; the code and `.env.example` use Gemini through `langchain-google-genai`. Do not change settings or provider.
- Open WebUI already points at `http://127.0.0.1:8000/v1`. Do **not** reinstall, reconfigure, modify, or build it.
- `langgraph` is already present in the virtual environment as a dependency of `langchain`. Check this with `uv pip show langgraph`. The only dependency change allowed is declaring it in `pyproject.toml`, in the next step below.
- Before editing, read `docs/architecture.md`, Stories 1.1–3.2, `.env.example`, and `src/learning_companion/` (`chain.py`, `main.py`, `config.py`). Preserve routes, settings, JSON and SSE response shapes, history handling, and `tests/test_health.py`.

## Work to do

Keep the change small. Add no endpoints, settings, providers, UI, storage, response fields, or Open WebUI plugins. Do not create a second app or chat route.

### 1. Declare the dependency

- Run `uv add langgraph`. Expect it to change only `pyproject.toml` and `uv.lock`, with no new packages installed. If it wants to install or upgrade anything else, stop and say so.

### 2. The state, in plain English (read before coding)

The graph state is one small typed dictionary with four fields:

| Field | Plain-English meaning | Written by |
| --- | --- | --- |
| `user_message` | The latest question the learner asked. The router replaces it with the marker-stripped text for the study route. | request, then router |
| `messages` | Earlier user and assistant messages from this request (the Story 2.2 history). Read-only in this story. | request |
| `route` | Which path was chosen: `general` or `study`. Empty until the router runs. | router |
| `answer` | The final reply text. Empty until an answer node runs. | answer nodes |

The state holds nothing else: no review notes, retry counters, tool results or stored memory.

### 3. `src/learning_companion/graph.py` (new file)

- Define `GraphState` as a `TypedDict` with `user_message: str`, `messages: list[BaseMessage]`, `route: str`, `answer: str`.
- Define `build_graph(general_chain, study_chain, trace=None)` that returns a compiled LangGraph `StateGraph`. The chains are passed in, so this file does not create models or read settings. `trace` is an optional callable taking one short string.
- Exactly three nodes, each with one responsibility:
  1. `router`: ordinary Python. Call the existing `select_route()` on `user_message`. Return `{"route": route, "user_message": question_for_chain}`. No model call.
  2. `general_chat`: call `general_chat_chain.invoke({"history": messages, "question": user_message})` and return `{"answer": text}`.
  3. `study_helper`: same, with the study-helper chain.
- Exactly these edges, written explicitly:
  - `START → router`
  - conditional edges from `router` to `general_chat` or `study_helper`, using a small function that returns `state["route"]`
  - `general_chat → END` and `study_helper → END`
- Do not add a reviewer, improver, loop, retry, extra node, checkpointer or persistence.
- Do not change the two chains or `select_route()`. The `/study` rules stay exactly as Story 3.2 defines them (`/studying`, a bare `/study` and a later `/study` stay general).
- Trace: each node calls `trace(...)` when one is given, with a compact line such as `graph: router -> study` or `graph: study_helper -> answer 412 chars`. Lines never contain the API key, the instructions, or message text.

### 4. `src/learning_companion/main.py`

- Remove the direct route choice (`select_route` call and the `if/else` on chains). Keep `split_conversation()`, the `ConfigurationError` handling (build both chains first, same error shape) and all response code.
- Build the graph with both chains. Pass `trace=print` only when `APP_ENV=development`, with flush on.
- Initial state: `{"user_message": question, "messages": history, "route": "", "answer": ""}`.
- Normal replies: run `graph.invoke(state)`, then use `result["route"]` for the label and `result["answer"]` as the text. Keep the same `[Route: ...]` label, JSON shape and `502` error shape.
- Streaming replies: keep the same SSE chunk shape. Run `graph.stream(state, stream_mode="messages")`, which lets model text pieces from inside the answer nodes come through, and send each piece through the existing `_chunk` helper. The route label is the first content chunk, as before, and is taken from the router's `route` (see the trace). If no pieces were streamed, send the final answer as one content chunk so the learner never sees an empty reply. Keep the existing stop chunk, `[DONE]` and in-stream error text.
  - If `stream_mode="messages"` does not produce pieces reliably, fall back to running `graph.invoke()` and sending the final answer as a single content chunk, and say so in the handover. Do not change the response format.
- Keep the existing development logging of history count, prompt roles and request messages. The route now appears in the graph trace rather than being decided in `main.py`.
- Do not change `/health`, `/v1/models`, request parsing or error shapes.

### 5. `docs/architecture.md`

Add a **Routing workflow (Story 4.1)** section and mark the Story 3.2 routing section as replaced. It must contain:

- the graph diagram:

  ```
  START → router ──general──→ general_chat → END
                 └──study────→ study_helper → END
  ```

- the four state fields above, in plain English;
- the node responsibilities (router = ordinary Python; two answer nodes = small specialist behaviours reusing the existing chains);
- the edge rules, including that the conditional edge reads `state["route"]`;
- the trace format, and that the final answer still passes through the existing JSON and SSE adapter;
- out of scope: reviewer, improver, loops, retries, tools, MCP, RAG, web search, persistence, human approval, more agents. These are for Story 4.2 or later, or not in the course at all.

Also update the **Stack** line and the **Boundaries** out-of-scope list so LangGraph is no longer listed as out of scope (agents, MCP and tool calls stay out), and update the **Chain behaviours** table to say the chains are now reached through graph nodes.

### Files this story changes

| File | Change |
| --- | --- |
| `src/learning_companion/graph.py` | new: state, three nodes, explicit edges |
| `src/learning_companion/main.py` | run the graph instead of the Python route; trace in development |
| `pyproject.toml`, `uv.lock` | declare `langgraph` (already installed) |
| `docs/architecture.md` | graph diagram, state, nodes, edges, trace, scope |

Do not change `chain.py`, `config.py`, `.env.example`, `study_dev.py`, `tests/test_health.py`, or Open WebUI. If one seems necessary, stop and say why.

### Out of scope

Reviewer or improver nodes, loops, retries, LLM-based routing, more agents, tool execution, MCP, RAG, web search, human approval, databases or persistence, checkpointers, a new endpoint, custom Open WebUI events or response fields, observability platforms, broad test suites, security work, and deployment.

## Completion checks

Run only these and report the real results:

```
uv add langgraph
uv run ruff format .
uv run ruff check .
uv run uvicorn learning_companion.main:app --app-dir src --host 127.0.0.1 --port 8000
```

With the server running (`APP_ENV=development`) and the real key in `.env`, use the existing Open WebUI chat:

1. **General path.** Send `Hi, how are you?`.
   - **Expected in Open WebUI:** a friendly reply starting with `[Route: general]`, without the study format.
   - **Expected trace:** `graph: router -> general`, then `graph: general_chat -> answer N chars`.
2. **Study path.** Send `/study Explain what an API is`.
   - **Expected in Open WebUI:** a reply starting with `[Route: study]` with a short explanation, a small example, and one next step.
   - **Expected trace:** `graph: router -> study`, then `graph: study_helper -> answer N chars`. The question the chain received no longer contains `/study`.
3. **Same connection.** Both final answers appear in the same Open WebUI conversation through `http://127.0.0.1:8000/v1`. Open WebUI normally streams, so these two messages cover the streaming path.
4. **Safe trace.** Neither trace nor log shows the API key or instruction text, and the trace shows no message text. (The existing development `REQUEST`/`RESPONSE` printouts from earlier stories are unchanged.)

Do not add a test suite, an evaluation harness or any other check.

## Handover

- List exactly which files changed and which commands were actually run, with outcomes. Include what `uv add langgraph` changed.
- Report what each Open WebUI message showed: the route label, the trace lines, and whether the study reply had an explanation, an example and one next step. If a check could not be run, say so plainly.
- State whether streaming sent model pieces progressively or used the single-chunk fallback.
- Confirm the endpoints, settings, provider, history handling and JSON/SSE shapes are unchanged apart from the existing label text, no key or instruction text was printed, and `.env` stays untracked.
- **Story 4.2 will extend this story** by adding a bounded review path to the same graph. It will reuse the same state, router, answer nodes and response adapter, and will add a reviewer and, at most, one limited improvement pass. No loop beyond that limit.
