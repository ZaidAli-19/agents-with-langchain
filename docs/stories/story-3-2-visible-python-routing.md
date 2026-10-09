# Story 3.2 — Visible Python Routing (`/study`)

## Purpose

Make both existing chains reachable from the same Open WebUI chat. One deliberately simple, visible Python rule chooses between them: a latest user message that begins with `/study` uses the study-helper chain, and everything else uses the general-chat chain. This is ordinary application code you can read in a few lines. Session 4 will later replace this `if/else` with an explicit LangGraph route.

Project path: the repository root (there is no `docs/config.yaml`).

## What this story implements in plain English

- A normal message such as "Hi, how are you?" takes the **general** path and gets the friendly Learning Companion reply, as before.
- A message starting with `/study`, such as `/study Explain what an API is`, takes the **study** path. The answer is a short explanation, a small example if useful, and one next step.
- Only the leading `/study` is removed before the question reaches the study-helper. Earlier messages in the same request still become history under the Story 2.2 rules.
- Each answer starts with a short label, `[Route: general]` or `[Route: study]`, and the terminal log shows the chosen route, so you can see which path ran.
- Both paths go through the same endpoint, the same Open WebUI chat, and the same normal and streaming response code. Nothing here classifies with an LLM or decides on its own; it is a plain `if` on the message text.

## Prerequisites

- Story 3.1 is complete: `build_study_helper_chain(settings)` exists in `src/learning_companion/chain.py`.
- Story 2.2 is complete: `split_conversation()`, `MAX_HISTORY_MESSAGES` and `build_chain(settings)` work.
- The untracked `.env` holds the existing key and model name. The configured provider is Gemini (the handout says "Grok"; the code says Gemini). Do not change settings or provider.
- Open WebUI already points at `http://127.0.0.1:8000/v1`. Do **not** reinstall, reconfigure, modify, or build it.
- Before editing, read `docs/architecture.md`, Stories 1.1–3.1, `.env.example`, and `src/learning_companion/` (`chain.py`, `main.py`, `config.py`). Preserve routes, settings, JSON and SSE response shapes, history handling, and `tests/test_health.py`.
- Do not install dependencies; everything needed is already installed.

## Work to do

Keep the change small. Add no dependencies, endpoints, settings, providers, UI, storage, response fields, or Open WebUI plugins.

### 1. `src/learning_companion/chain.py` (add only)

- Leave both chain builders, both instructions, `split_conversation()` and `MAX_HISTORY_MESSAGES` as they are.
- Add `STUDY_MARKER = "/study"` and a small function `select_route(question: str) -> tuple[str, str]` returning `(route, question_for_chain)`:
  - If the question, after removing leading whitespace, starts with `/study` and the next character is whitespace (or the text ends there), and some text remains after the marker, return `("study", remaining text stripped)`.
  - Otherwise return `("general", question)` unchanged. This covers `/studying`, `/study` with nothing after it, and ordinary messages.
  - Only the leading marker is removed; `/study` appearing later in the text is left alone.
- Routing looks at the latest user message only. Messages in history are not rewritten, even if they began with `/study`.

### 2. `src/learning_companion/main.py`

- After `split_conversation()`, call `select_route(question)`, then build the chain for that route (`build_study_helper_chain(settings)` for `study`, `build_chain(settings)` for `general`). Keep the existing `ConfigurationError` handling.
- Use the same chain input shape for both routes: `{"history": history, "question": question_for_chain}`.
- Development log: extend the existing one-line dev print to include `route: general` or `route: study`. Never log keys, the instruction text, or message text. The route is logged only when `APP_ENV=development`, like the current line.
- Route label in the answer text: prefix the reply with `[Route: general]` or `[Route: study]` followed by a blank line.
  - Non-streaming: prepend it to the text in `message.content`.
  - Streaming: emit the label as the first `content` chunk, then the model pieces.
  - The response fields and shapes stay exactly as they are. The label is plain text only.
- Keep the label in a single place (one small helper or constant) so it is easy to remove later.
- Do not change the `/v1/models` or `/health` routes, request parsing, or error shapes.

### 3. `docs/architecture.md`

- Add a short **Routing (Story 3.2)** section covering:
  - the rule: latest user message starting with `/study` → study-helper chain, otherwise the general-chat chain;
  - the path: `Open WebUI request → split history/question → select_route → chosen chain → existing JSON or SSE adapter`;
  - the label and development log line;
  - the boundary: this is deterministic application routing, not LLM classification, LangGraph, or multi-agent orchestration.
- Update the **Chain behaviours** table: the study helper is now used by the Open WebUI endpoint for `/study` messages.

### Files this story changes

| File | Change |
| --- | --- |
| `src/learning_companion/chain.py` | add `STUDY_MARKER` and `select_route()` |
| `src/learning_companion/main.py` | choose the chain by route, log route, add route label |
| `docs/architecture.md` | routing section, chain behaviours update |

Do not change `config.py`, `.env.example`, `pyproject.toml`, `uv.lock`, `study_dev.py`, or Open WebUI. If one seems necessary, stop and say why.

### Out of scope

LLM-based routing or classification, more specialists, review steps, loops, tools, retrieval, MCP, LangGraph, agents, a new endpoint, custom response fields, Open WebUI plugins, a model provider change, a database, UI, broad tests, or production controls.

## Completion checks

Run only these and report the real results:

```
uv run ruff format .
uv run ruff check .
uv run uvicorn learning_companion.main:app --app-dir src --host 127.0.0.1 --port 8000
```

With the server running (`APP_ENV=development`) and the real key in `.env`, use the existing Open WebUI chat:

1. **General route.** Send `Hi, how are you?`. **Expected:** a friendly reply starting with `[Route: general]`, with no forced study structure. The terminal log shows `route: general`.
2. **Study route.** Send `/study Explain what an API is`. **Expected:** a reply starting with `[Route: study]` with a clear plain-English explanation, a small example if useful, and exactly one next step. The terminal log shows `route: study`, and the question the chain received no longer contains `/study`.
3. **Same endpoint.** Both replies arrive in the same Open WebUI conversation through `http://127.0.0.1:8000/v1`. Open WebUI normally streams, so the streaming path is covered by these two messages.

Do not add LLM routing, a test suite, or an evaluation harness.

## Handover

- List exactly which files changed and which commands were actually run, with outcomes.
- State what each Open WebUI message showed: the route label, the log line, and whether the study reply had an explanation and one next step. If a check could not be run, say so plainly.
- Confirm the JSON and SSE response shapes, endpoints, settings and history handling are unchanged apart from the label text, no key or instruction text was printed, and `.env` stays untracked.
- **Story 4.1 will extend this story** by replacing the Python `if/else` with an explicit LangGraph route that makes the same choice, reusing the same two chains and the same history handling.
