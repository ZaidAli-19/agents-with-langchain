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
    build_improver_chain,
    build_reviewer_chain,
    build_study_helper_chain,
    prompt_roles,
    split_conversation,
)
from learning_companion.config import get_settings
from learning_companion.graph import build_graph

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
    # History comes only from this request; `system` messages are never used.
    history, question = split_conversation(request.messages)
    try:
        general_chain = build_chain(settings)
        study_chain = build_study_helper_chain(settings)
        reviewer_chain = build_reviewer_chain(settings)
        improver_chain = build_improver_chain(settings)
    except ConfigurationError as exc:
        return _error(str(exc), 500, "configuration_error")

    dev = settings.app_env == "development"
    graph = build_graph(
        general_chain,
        study_chain,
        reviewer_chain,
        improver_chain,
        trace=(lambda line: print(line, flush=True)) if dev else None,
    )
    state = {
        "user_message": question,
        "messages": history,
        "route": "",
        "draft_answer": "",
        "review_decision": "",
        "review_reason": "",
        "revision_count": 0,
        "final_answer": "",
    }
    if dev:
        print(
            f"history: {len(history)} of {MAX_HISTORY_MESSAGES} max; "
            f"prompt roles: {prompt_roles(history, question)}; "
            f"request messages: {len(request.messages)}",
            flush=True,
        )
        _dev_print(
            "REQUEST",
            {
                "question": question,
                "history": [{"role": m.type, "content": m.content} for m in history],
            },
        )
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"

    if not request.stream:
        try:
            result = graph.invoke(state)
        except Exception as exc:  # noqa: BLE001
            return _error(f"Model call failed: {exc}", 502, "upstream_error")
        text = f"[Route: {result['route']}]\n\n" + result["final_answer"]
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
            # Drafts may be replaced by the improver, so only the label and final answer are sent.
            for update in graph.stream(state, stream_mode="updates"):
                if "router" in update:
                    piece = f"[Route: {update['router']['route']}]\n\n"
                elif update.get("reviewer", {}).get("final_answer"):
                    piece = update["reviewer"]["final_answer"]
                else:
                    continue
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
