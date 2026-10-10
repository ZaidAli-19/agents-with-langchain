# Manual Tests

## Story 1.1 — Architecture and Project Seed

**What it adds:** a local OpenAI-compatible API (`/health`, `/v1/models`, `/v1/chat/completions`) that answers through a LangChain prompt and Gemini.

Prerequisite: start the API with `uv run uvicorn learning_companion.main:app --app-dir src --host 127.0.0.1 --port 8000`, with `GEMINI_API_KEY` and `GEMINI_MODEL_NAME` set in your untracked `.env`.

```bash
curl http://127.0.0.1:8000/health
```

Expected: `200` with `{"status":"ok"}`.

```bash
curl http://127.0.0.1:8000/v1/models
```

Expected: `200`, `"object":"list"`, with one model whose `id` is your `GEMINI_MODEL_NAME` (default `gemini-3.5-flash-lite`).

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.5-flash-lite","stream":false,"messages":[{"role":"user","content":"Explain what a variable is in one sentence."}]}'
```

Expected: `200`, `"object":"chat.completion"`, `choices[0].message.content` holds a short Gemini answer, and `finish_reason` is `stop`. With `GEMINI_API_KEY` blank it returns `500` with `error.type` `configuration_error` instead.

```bash
curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.5-flash-lite","stream":true,"messages":[{"role":"user","content":"Explain what a variable is in one sentence."}]}'
```

Expected: `data:` lines with `"object":"chat.completion.chunk"` carrying text pieces in `delta.content`, then a chunk with `finish_reason` `stop`, ending with `data: [DONE]`.

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.5-flash-lite","stream":false,"messages":[{"role":"tool","content":"hi"}]}'
```

Expected: `422` validation error, because `tool` is not an allowed role (`system`, `user` or `assistant`).

## Story 4.2 — Bounded Review and Improve

**What it adds:** after the routed answer node writes a draft, a reviewer checks it once and an improver may rewrite it at most once, so `/v1/chat/completions` returns only the final answer, prefixed with `[Route: general]` or `[Route: study]`.

Prerequisite: start the API as in Story 1.1 with `APP_ENV=development` to see the `graph:` trace lines in the server terminal (e.g. `graph: reviewer -> approve (revision 0): ...`). Replies take longer because one question can make up to three model calls.

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.5-flash-lite","stream":false,"messages":[{"role":"user","content":"/study Explain recursion, closures and decorators"}]}'
```

Expected: `200`, `"object":"chat.completion"`, `choices[0].message.content` starts with `[Route: study]` followed by Explanation, Example and one Next step. The trace shows `reviewer` then, if it said `improve`, one `improver -> revision 1` and `reviewer -> approve (revision 1): revision limit reached`; `improver` never appears twice. The reviewer is an LLM, so it may approve the first draft directly.

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.5-flash-lite","stream":false,"messages":[{"role":"user","content":"Hi, how are you?"}]}'
```

Expected: `200`, content starts with `[Route: general]` and is a short friendly reply; the trace normally shows `reviewer -> approve (revision 0)`.

```bash
curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.5-flash-lite","stream":true,"messages":[{"role":"user","content":"/study Explain APIs, databases, caching and queues"}]}'
```

Expected: `chat.completion.chunk` lines: a role chunk, one content chunk `[Route: study]`, one content chunk holding the whole final answer (no draft text, not word by word), a chunk with `finish_reason` `stop`, then `data: [DONE]`.

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini-3.5-flash-lite","stream":false,"messages":[{"role":"user","content":"/study"}]}'
```

Expected: `200`; `/study` with no text is not a study request, so it is routed as `[Route: general]`. With `GEMINI_API_KEY` blank, any of these returns `500` with `error.type` `configuration_error`.
