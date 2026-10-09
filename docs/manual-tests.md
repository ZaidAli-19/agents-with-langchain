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
