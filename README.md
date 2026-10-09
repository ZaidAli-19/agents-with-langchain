# Learning Companion Chatbot

A small local API that lets the already-installed Open WebUI chat with Gemini through LangChain.

`Open WebUI → this app's /v1/chat/completions → LangChain prompt and Gemini model → answer in Open WebUI`

See [docs/architecture.md](docs/architecture.md). Do not reinstall, reconfigure, or modify Open WebUI.

## Setup

1. Install Python 3.12 and [UV](https://docs.astral.sh/uv/).
2. `uv sync`
3. Copy `.env.example` to `.env`. Put your real Gemini key in `GEMINI_API_KEY` and the model name your instructor gave you in `GEMINI_MODEL_NAME`. `.env` is untracked; never commit it.

## Run

```
uv run uvicorn learning_companion.main:app --app-dir src --host 127.0.0.1 --port 8000
```

The app starts even without a key. A chat request without a key or model name returns a clear configuration error.

Check it:

```
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/models
```

## Connect Open WebUI

Only the application-side values change in your existing Open WebUI connection:

- Base URL: `http://127.0.0.1:8000/v1` (if Open WebUI runs in Docker, use `http://host.docker.internal:8000/v1`)
- Model: pick the model listed by this app (your `GEMINI_MODEL_NAME`)

## Lint

```
uv run ruff format .
uv run ruff check .
```
