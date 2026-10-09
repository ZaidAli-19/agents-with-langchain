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
src/learning_companion/   config.py, chain.py, main.py
tests/
.env.example  .gitignore  pyproject.toml  uv.lock  README.md
```

## Configuration

Settings: `APP_ENV`, `GEMINI_API_KEY`, `GEMINI_MODEL_NAME`, `HOST`, `PORT`. The default model is `gemini-3.5-flash-lite`; participants put their real key only in an untracked `.env`. The app starts without a key and reports a configuration error only when a model call is attempted.

## Boundaries

- API keys stay in an untracked `.env`.
- Application instructions stay separate from user messages.
- Out of scope: authentication, authorization, security hardening, databases, persistent memory, RAG, production deployment, extensive tests, tool calls, LangGraph, agents, MCP.

## Message flow (Story 2.1)

`Open WebUI request → latest user message → [system: application instruction][human: user message] → Gemini model → text output → OpenAI-compatible JSON or SSE`

- The prompt is a LangChain chat prompt (`build_prompt()` in `chain.py`) with a fixed system message owned by the application and one human message.
- The same chain serves normal (`invoke`) and streaming (`stream`) requests.
- A request-supplied `system` message is treated as user content and never replaces the application instruction; it is ignored in this story.
- In development (`APP_ENV=development`) one log line shows prompt message roles and counts, never keys or message text.

## No-persistence boundary

The application keeps nothing between requests: no history, database, or memory. Only the latest user message is used. Story 2.2 adds conversation history from the request's earlier messages.
