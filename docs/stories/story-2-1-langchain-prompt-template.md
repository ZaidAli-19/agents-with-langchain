# Story 2.1 — LangChain Prompt Template

## Purpose

Make the seed's LangChain flow reusable and easy to read. Replace the seed's fixed latest-message prompt with a small chat prompt that keeps two parts clearly apart: the application's stable Learning Companion instruction and the participant's current message. The endpoints, response behaviour, model settings, and Open WebUI connection stay exactly as they are.

Project path: the repository root (there is no `docs/config.yaml`).

## What this story implements in plain English

After this story, a participant can:

- Chat in Open WebUI exactly as before; the same model is selected and answers appear the same way.
- Get replies that always follow the same Learning Companion instruction, which the application owns and a chat message cannot replace.
- Type their own "system" text in a message and have it treated as ordinary text from them, not as a new set of rules.
- Ask a question and know the application answers from that latest message only; remembering earlier messages comes in the next story.
- Let the instructor see, in the development terminal, a short line showing which message roles reached the prompt and how many, with no secrets shown.

## Prerequisites

- Story 1.1 is complete: `GET /health`, `GET /v1/models`, and `POST /v1/chat/completions` work, and Open WebUI already talks to `http://127.0.0.1:8000/v1`.
- A real model key and the model name are set in the untracked `.env` (existing `GEMINI_API_KEY` and `GEMINI_MODEL_NAME`; the repository's configured model provider is Gemini through `langchain-google-genai`).
- Open WebUI is installed and working. Do **not** reinstall, reconfigure, modify, or build it.
- Before editing, read `docs/architecture.md`, Story 1.1, `.env.example`, and `src/learning_companion/` (`chain.py`, `main.py`, `config.py`). Preserve existing work, routes, settings, and tests.
- Create the story only when handed over; this document does not itself change application code.

## Work to do

Keep the change small. Add no dependencies (`langchain-core` is already installed via `langchain`).

### 1. `src/learning_companion/chain.py`

- Keep `ConfigurationError`, the missing-key and missing-model checks, and the model construction from `Settings` unchanged.
- Move the stable Learning Companion instruction into a clearly named constant owned by the application (reuse the existing `LEARNING_COMPANION_INSTRUCTION` text).
- Build the prompt with LangChain chat-prompt abstractions, for example `ChatPromptTemplate.from_messages([SystemMessage(content=LEARNING_COMPANION_INSTRUCTION), HumanMessagePromptTemplate.from_template("{question}")])`, or an equivalent that makes the two parts obvious:
  1. system part: the fixed instruction (a fixed message, not a template variable, so user text can never fill it);
  2. human part: the current user message.
- Do not build the prompt by joining strings.
- Expose the prompt as its own small function or constant (for example `build_prompt()`), so it can be inspected without calling the model.
- Keep one chain, `prompt | model | StrOutputParser()`, returned by `build_chain(settings)`.

### 2. `src/learning_companion/main.py`

- Keep the three routes, request and response shapes, JSON and SSE behaviour, error responses, and `Message`/`ChatRequest` models.
- Use only the **latest supported `user` message** as the question. Earlier user messages, `assistant` messages, and history are ignored in this story.
- A request-supplied `system` message is user-provided content. It must never replace or extend the application's instruction. It is ignored for prompt construction in this story (it is not placed in the system slot).
- Pass the question to the same `chain` for both `chain.invoke(...)` (normal) and `chain.stream(...)` (streaming). No second chat path.
- Add a compact development-only log, shown only when `APP_ENV=development`: one line per request listing the roles and count of the prompt messages in order (for example `prompt messages: 2 [system, human]; request messages: 3`). It must never print the API key, the full application instruction, or full message text.
- If a small inspectable helper is easier than logging, add it next to `build_prompt()` (for example a function returning the ordered message roles) and have the log call it.

### 3. `docs/architecture.md`

- Replace the "Seed flow and what comes next" section with the Story 2.1 message flow:
  `Open WebUI request → latest user message → [system: application instruction][human: user message] → model → text output → OpenAI-compatible JSON or SSE`.
- State the deliberate **no-persistence boundary**: the application keeps nothing between requests; no history, database, or memory.
- State that a request-supplied `system` message is treated as user content.
- Say that history handling is added in Story 2.2.

### Files this story changes

| File | Change |
| --- | --- |
| `src/learning_companion/chain.py` | LangChain chat prompt with separate system and human parts; inspectable prompt helper |
| `src/learning_companion/main.py` | Latest-user-message handling, `system` treated as user content, compact development log |
| `docs/architecture.md` | Message flow and no-persistence boundary |

Do not change `config.py`, `.env.example`, `pyproject.toml`, `uv.lock`, routes, or Open WebUI. If a change to any of these seems necessary, stop and say why.

### Out of scope

Command-line-only chatbot, a second chat path, conversation history, database, persistent memory, RAG, tools, MCP, LangGraph, a new frontend, an evaluation harness, a broad test suite, production memory, or a security programme.

## Completion checks

Run only these and report the real results:

```
uv run ruff format .
uv run ruff check .
uv run uvicorn learning_companion.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Then, with the server running and the real key in `.env`, in the existing Open WebUI:

1. Select the model listed by `GET /v1/models`.
2. Send one ordinary question, for example "What is a variable?".
3. Confirm the development terminal shows the prompt roles in the expected order, system first and then the user message (for example `[system, human]`), with no key and no full instruction text.
4. Confirm Open WebUI still renders the answer, in the same friendly, simple style.

**Expected Open WebUI result:** one normal answer to the question appears in the chat window, as it did after Story 1.1.

Do not add or run a full test suite. The existing `tests/test_health.py` may be left as it is.

## Handover

- List exactly which files changed and which commands were actually run, with outcomes.
- State whether the Open WebUI check passed, and whether the logged order was system, then human. If it could not be run, say so plainly.
- Confirm no API key or full instruction text appears in logs, and that `.env` stays untracked.
- **Story 2.2 will extend this story** by adding conversation history from the request's earlier messages into the same prompt on the same chat endpoint, keeping the application's instruction separate.
