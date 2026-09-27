"""Web endpoint the iPhone Shortcut calls.

Run with:  uvicorn assistant.server:app --host 0.0.0.0 --port 8000
"""

import hmac
import threading

import anthropic
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import config
from .agent import Assistant
from .gmail_client import GmailClient

if not config.ASSISTANT_TOKEN:
    raise RuntimeError("Set ASSISTANT_TOKEN in .env before starting the server.")

app = FastAPI(title="My-Ai voice assistant")
_assistant = Assistant(anthropic.Anthropic(), GmailClient())
_lock = threading.Lock()  # one conversation, so handle one request at a time


class AskRequest(BaseModel):
    text: str


class AskResponse(BaseModel):
    speech: str


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, authorization: str = Header(default="")) -> AskResponse:
    expected = f"Bearer {config.ASSISTANT_TOKEN}"
    if not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    with _lock:
        return AskResponse(speech=_assistant.handle(req.text))
