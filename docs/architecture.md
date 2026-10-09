# Architecture — Learning Companion Chatbot

## Classroom flow

`Open WebUI → this local application’s OpenAI-compatible chat endpoint → LangChain prompt and Gemini model → answer in Open WebUI`

## Open WebUI

Open WebUI is already installed and working for participants. It is the supplied chat client only. Participants must not reinstall, reconfigure, modify, or build it. The only application-side change allowed is pointing its existing connection at this app's local base URL (`http://127.0.0.1:8000/v1`) and selecting the model.

## Capstone

A small **Learning Companion Chatbot**. There is no custom frontend and no second demonstration application.

## Endpoints

| Route | Purpose |
| --- | --- |
| `GET /health` | Simple OK check |
| `GET /v1/models` | OpenAI-compatible list exposing the configured Gemini model |
| `POST /v1/chat/completions` | OpenAI-compatible chat; JSON when `stream` is false, text-only SSE chunks, stop chunk and `[DONE]` when true |

No custom Open WebUI events and no second chat route.

## Stack

Python 3.12, UV, FastAPI, Uvicorn, Pydantic settings, `langchain`, `langgraph`, the Gemini LangChain integration (`langchain-google-genai`), Ruff, and a minimal test runner.

## Planned layout

```
src/learning_companion/   config.py, chain.py, main.py, study_dev.py
tests/
.env.example  .gitignore  pyproject.toml  uv.lock  README.md
```

## Configuration

Settings: `APP_ENV`, `GEMINI_API_KEY`, `GEMINI_MODEL_NAME`, `HOST`, `PORT`. The default model is `gemini-3.5-flash-lite`; participants put their real key only in an untracked `.env`. The app starts without a key and reports a configuration error only when a model call is attempted.

## Boundaries

- API keys stay in an untracked `.env`.
- Application instructions stay separate from user messages.
- Out of scope: authentication, authorization, security hardening, databases, persistent memory, RAG, production deployment, extensive tests, tool calls, agents, MCP.

## Message flow (Story 2.2)

`Open WebUI request → earlier user/assistant messages (last 10) + latest user message → [system: application instruction][history][human: latest question] → Gemini model → text output → OpenAI-compatible JSON or SSE`

- The prompt is a LangChain chat prompt (`build_prompt()` in `chain.py`): a fixed system message owned by the application, a `MessagesPlaceholder("history")`, then the human message.
- History is the supported prior `user` and `assistant` messages from the current request, in original order, limited to `MAX_HISTORY_MESSAGES = 10`.
- The same chain serves normal (`invoke`) and streaming (`stream`) requests.
- A request-supplied `system` message never replaces the application instruction and is not used as history. Unsupported or empty content is ignored.
- In development (`APP_ENV=development`) one log line shows history count, prompt roles, and request message count, never keys, the instruction, or message text.

## Chain behaviours

| Behaviour | Where | Responsibility | Used by |
| --- | --- | --- | --- |
| General chat | `build_chain` | Friendly Learning Companion for greetings and ordinary conversation | General-chat graph node |
| Study helper | `build_study_helper_chain` | Plain-language beginner explanation, a small example where useful, one next step | Study-helper graph node (`/study` messages); also the local dev command |

Both use the same configured model, the same request-provided history shape, the same OpenAI-compatible endpoint, and the same Open WebUI chat. Story 3.1 creates the study-helper capability only (try it with `uv run python -m learning_companion.study_dev "What is an API?"`); selecting between the chains is Story 3.2.

## Routing (Story 3.2, replaced by Story 4.1)

`Open WebUI request → split history/question → select_route → chosen chain → existing JSON or SSE adapter`

- Rule (`select_route()` in `chain.py`): if the latest user message begins with `/study` followed by text, use the study-helper chain with the leading marker removed; otherwise use the general-chat chain. `/studying`, a bare `/study`, and a `/study` later in the text stay general.
- History handling is unchanged (Story 2.2); earlier messages are not rewritten.
- Each answer starts with a plain-text label, `[Route: general]` or `[Route: study]`. Response fields and shapes are unchanged. In development the log line also shows `route: general|study`.
- Boundary: this is deterministic application routing, not LLM classification, LangGraph, or multi-agent orchestration. Story 4.1 replaced the `if/else` in `main.py` with the LangGraph workflow below; `select_route()` is now called by the router node.

## Routing workflow (Story 4.1)

`Open WebUI request → split history/question → graph → existing JSON or SSE adapter`

```
START → router ──general──→ general_chat → END
               └──study────→ study_helper → END
```

Code: `src/learning_companion/graph.py` (`GraphState`, `build_graph`). `main.py` builds the graph per request from the two existing chains.

**State** (the shared notepad, a typed dict):

| Field | Meaning |
| --- | --- |
| `user_message` | Latest question; the router replaces it with the marker-stripped text for `/study` |
| `messages` | Earlier user/assistant messages from this request (Story 2.2 history), read-only |
| `route` | `general` or `study`; empty until the router runs |
| `answer` | Final reply; empty until an answer node runs |

**Nodes** (a node is a focused piece of work, not automatically an agent):

- `router`: ordinary Python, no model call. Uses `select_route()` and writes `route`.
- `general_chat`: calls the general-chat chain, writes `answer`.
- `study_helper`: calls the study-helper chain, writes `answer`.

The two answer nodes are small specialist behaviours. An MCP or other tool call could sit inside a future node; none is implemented.

**Edges:** `START → router`; conditional edge from `router` reading `state["route"]` to `general_chat` or `study_helper`; each answer node `→ END`.

**Output and trace:** the final answer and route label go through the unchanged JSON and SSE adapter (streaming uses LangGraph `stream_mode` messages, with the final answer sent as one chunk if no pieces stream). In development one line per node is printed, for example `graph: router -> study`, then `graph: study_helper -> answer 414 chars`. Lines contain no keys, instructions or message text.

**Out of scope:** reviewer, improver, loops, retries (bounded review is Story 4.2), tools, MCP, RAG, web search, persistence, human approval, more agents.

## No-persistence boundary

History comes only from the current Open WebUI request. The application saves nothing after a request ends: no database, cross-session or persistent memory.
