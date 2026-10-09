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

Python 3.12, UV, FastAPI, Uvicorn, Pydantic settings, `langchain`, the Gemini LangChain integration (`langchain-google-genai`), Ruff, and a minimal test runner.

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
- Out of scope: authentication, authorization, security hardening, databases, persistent memory, RAG, production deployment, extensive tests, tool calls, LangGraph, agents, MCP.

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
| General chat | `build_chain` | Friendly Learning Companion for greetings and ordinary conversation | Open WebUI endpoint (unchanged) |
| Study helper | `build_study_helper_chain` | Plain-language beginner explanation, a small example where useful, one next step | Open WebUI endpoint for `/study` messages; also the local dev command |

Both use the same configured model, the same request-provided history shape, the same OpenAI-compatible endpoint, and the same Open WebUI chat. Story 3.1 creates the study-helper capability only (try it with `uv run python -m learning_companion.study_dev "What is an API?"`); selecting between the chains is Story 3.2.

## Routing (Story 3.2)

`Open WebUI request → split history/question → select_route → chosen chain → existing JSON or SSE adapter`

- Rule (`select_route()` in `chain.py`): if the latest user message begins with `/study` followed by text, use the study-helper chain with the leading marker removed; otherwise use the general-chat chain. `/studying`, a bare `/study`, and a `/study` later in the text stay general.
- History handling is unchanged (Story 2.2); earlier messages are not rewritten.
- Each answer starts with a plain-text label, `[Route: general]` or `[Route: study]`. Response fields and shapes are unchanged. In development the log line also shows `route: general|study`.
- Boundary: this is deterministic application routing, not LLM classification, LangGraph, or multi-agent orchestration. Story 4.1 replaces the `if/else` with an explicit LangGraph route.

## No-persistence boundary

History comes only from the current Open WebUI request. The application saves nothing after a request ends: no database, cross-session or persistent memory.
