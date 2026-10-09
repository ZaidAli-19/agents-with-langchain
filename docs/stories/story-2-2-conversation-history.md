# Story 2.2 — Conversation History

## Purpose

Let a follow-up question use the earlier messages of the same chat. Open WebUI already sends the active chat's messages with every request; this story passes a small, recent slice of them into the existing prompt, between the application's instruction and the latest question. Nothing is stored. Endpoints, response shapes, model configuration, the prompt → model → text-output chain, and the Open WebUI connection stay as they are.

Project path: the repository root (there is no `docs/config.yaml`).

## What this story implements in plain English

After this story, a participant can:

- Ask a question, then ask "Can you give an example of that?" and get an answer that makes sense, because the earlier messages travel with the new one.
- Rely on the chat window, not the application, to supply those earlier messages. The application remembers nothing once a reply is finished.
- Know that only the most recent messages (a small, fixed number) are used, so very long chats are trimmed from the oldest end.
- Still get the same Learning Companion rules every time; a "system" message typed or sent in a request never replaces them.
- Let the instructor see in the development terminal which message roles were used and how many, without seeing keys or full text.

## Prerequisites

- Story 2.1 is complete: `build_prompt()` in `chain.py` has the fixed system instruction and one human message, and `prompt | model | StrOutputParser()` serves both JSON and SSE replies.
- The untracked `.env` holds the existing model key and name. The repository's configured provider is Gemini via `langchain-google-genai` (the handout calls it "Grok"; the code and `.env.example` say Gemini). Keep the existing configuration unchanged and do not switch providers.
- Open WebUI is installed and already points at `http://127.0.0.1:8000/v1`. Do **not** reinstall, reconfigure, modify, or build it.
- Before editing, read `docs/architecture.md`, Stories 1.1 and 2.1, `.env.example`, and `src/learning_companion/` (`chain.py`, `main.py`, `config.py`). Preserve routes, settings, and `tests/test_health.py`.
- This document only describes the work. Do not install dependencies; `langchain-core` is already available.

## Work to do

Keep the change small. Add no dependencies, endpoints, settings, or UI.

### 1. `src/learning_companion/chain.py`

- Keep `ConfigurationError`, the key and model-name checks, model construction, and `LEARNING_COMPANION_INSTRUCTION` unchanged.
- Add a documented constant `MAX_HISTORY_MESSAGES = 10` (the most recent prior messages used, counting both `user` and `assistant`).
- Change `build_prompt()` to three parts, in this order: the fixed `SystemMessage`, a `MessagesPlaceholder("history")`, then `HumanMessagePromptTemplate.from_template("{question}")`. Do not join strings to build a prompt.
- Add a small helper, for example `to_history(messages)`, that turns request messages into LangChain messages:
  - `user` → `HumanMessage`, `assistant` → `AIMessage`, in their original order;
  - skip `system` messages and any message whose content is not non-empty plain text;
  - keep only the last `MAX_HISTORY_MESSAGES`.
- Update the dev-only inspectable helper (the existing `prompt_roles`) to take history and question and return ordered roles only, for example `[system, human, ai, human]`. Remove `prompt_messages`, which prints message text.
- Keep one chain returned by `build_chain(settings)`.

### 2. `src/learning_companion/main.py`

- Keep the three routes, error responses, JSON and SSE behaviour, and the `ChatRequest` shape. Allow `Message.content` to be `str | list | None` so Open WebUI content the app does not support is ignored rather than rejected; only plain text is ever used.
- The **question** is the latest supported `user` message. The **history** is the supported `user` and `assistant` messages that come **before** it, through `to_history(...)`.
- Call `chain.invoke({"history": history, "question": question})` for normal replies and `chain.stream({...same input...})` for streaming. No second chat path.
- Replace the full-request and full-prompt dev dumps with one compact line, only when `APP_ENV=development`, for example:
  `history: 4 of 10 max; prompt roles: [system, human, ai, human, ai, human]; request messages: 7`
  Never log the API key, the application instruction, or message bodies. The existing `RESPONSE` dev print may stay if it is short.
- A request-supplied `system` message is never placed in the system slot and never used as history.

### 3. `docs/architecture.md`

- Replace the Story 2.1 "Message flow" and "No-persistence boundary" sections with:
  `Open WebUI request → earlier user/assistant messages (last 10) + latest user message → [system: application instruction][history][human: latest question] → model → text output → OpenAI-compatible JSON or SSE`
- State the limit (`MAX_HISTORY_MESSAGES = 10`) and that history comes only from the current request.
- State the boundary: nothing is saved after a request ends; no database, cross-session or persistent memory.
- Keep the note that request `system` messages never replace the application instruction.
- Update the dev-log description to roles and counts only.

### Files this story changes

| File | Change |
| --- | --- |
| `src/learning_companion/chain.py` | message placeholder, history limit, history helper, roles helper |
| `src/learning_companion/main.py` | build history and question, pass both to the chain, compact dev log |
| `docs/architecture.md` | request-provided history flow, limit, no-persistence boundary |

Do not change `config.py`, `.env.example`, `pyproject.toml`, `uv.lock`, routes, or Open WebUI. If one seems necessary, stop and say why.

### Out of scope

Database, persistent or cross-session memory, summarising, RAG, tools, MCP, routing, LangGraph, a new endpoint or UI, an evaluation harness, a broad test suite, production memory features.

## Completion checks

Run only these and report the real results:

```
uv run ruff format .
uv run ruff check .
uv run uvicorn learning_companion.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Then, with the server running and the real key in `.env`, in the existing Open WebUI, start a **new chat** and select the model listed by `GET /v1/models`:

1. Send: "What is a variable? Answer in two sentences."
2. Send: "Can you give me one tiny example of what you just explained?"
3. Check the development terminal: the second request shows roles in the order `[system, human, ai, human]`, history count 2, and no key, no instruction text, and no message bodies.

**Expected Open WebUI result:** the first answer explains variables. The second answer gives a small example of a variable (for instance `age = 12`) without asking what "that" refers to, and keeps the friendly, simple style. Replies appear normally whether Open WebUI streams or not.

Do not add an evaluation harness or a broad test suite.

## Handover

- List exactly which files changed and which commands were actually run, with outcomes.
- State whether the two-turn Open WebUI check passed, the role sequence logged, and whether the follow-up used the earlier context. If it could not be run, say so plainly.
- Confirm no key, instruction text, or message bodies appear in logs, and that `.env` stays untracked.
- State the history limit used and that nothing is stored after a request.
- **Story 3.1 will extend this story** by building on the same prompt-with-history chain; this story adds no persistence, retrieval, or tools to carry forward.
