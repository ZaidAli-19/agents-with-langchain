import json
import time
import uuid
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from learning_companion.chain import (
    MAX_HISTORY_MESSAGES,
    ConfigurationError,
    build_chain,
    prompt_roles,
    split_conversation,
)
from learning_companion.config import get_settings

app = FastAPI(title="Learning Companion Chatbot")


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | list | None = None


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    stream: bool = False


def _error(message: str, status: int, kind: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"message": message, "type": kind, "code": None}}
    )


def _chunk(completion_id: str, model: str, delta: dict, finish: str | None) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload)}\n\n"


def _dev_print(title: str, data) -> None:
    """Development only: pretty-print to the terminal. Never includes the API key."""
    print(f"\n===== {title} =====\n{json.dumps(data, indent=2, ensure_ascii=False)}", flush=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/models")
def list_models():
    name = get_settings().gemini_model_name
    data = [{"id": name, "object": "model", "created": 0, "owned_by": "google"}] if name else []
    return {"object": "list", "data": data}


@app.post("/v1/chat/completions")
def chat_completions(request: ChatRequest):
    settings = get_settings()
    try:
        chain = build_chain(settings)
    except ConfigurationError as exc:
        return _error(str(exc), 500, "configuration_error")

    # History comes only from this request; `system` messages are never used.
    history, question = split_conversation(request.messages)
    chain_input = {"history": history, "question": question}
    dev = settings.app_env == "development"
    if dev:
        print(
            f"history: {len(history)} of {MAX_HISTORY_MESSAGES} max; "
            f"prompt roles: {prompt_roles(history, question)}; "
            f"request messages: {len(request.messages)}",
            flush=True,
        )
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"

    if not request.stream:
        try:
            text = chain.invoke(chain_input)
        except Exception as exc:  # noqa: BLE001
            return _error(f"Model call failed: {exc}", 502, "upstream_error")
        if dev:
            _dev_print("RESPONSE", {"role": "assistant", "content": text})
        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        }

    def events():
        yield _chunk(completion_id, request.model, {"role": "assistant"}, None)
        pieces: list[str] = []
        try:
            for piece in chain.stream(chain_input):
                if piece:
                    pieces.append(piece)
                    yield _chunk(completion_id, request.model, {"content": piece}, None)
            if dev:
                _dev_print("RESPONSE (streamed)", {"role": "assistant", "content": "".join(pieces)})
        except Exception as exc:  # noqa: BLE001
            yield _chunk(
                completion_id, request.model, {"content": f"[Model call failed: {exc}]"}, None
            )
        yield _chunk(completion_id, request.model, {}, "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
