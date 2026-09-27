"""Thin wrapper around the Gmail API: search, read, and send."""

import base64
import html
import re
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from . import config

MAX_BODY_CHARS = 8000


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


def _extract_text(payload: dict) -> str:
    """Return the plain-text body, falling back to HTML with tags stripped."""
    plain, rich = [], []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            rich.append(_decode(data))
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    if plain:
        return "\n".join(plain)
    text = re.sub(r"<(script|style).*?</\1>", " ", "\n".join(rich), flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


class GmailClient:
    def __init__(self, token_file: str = config.GMAIL_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(token_file, config.GMAIL_SCOPES)
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        self._svc = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        resp = (
            self._svc.users()
            .messages()
            .list(userId="me", q=query, maxResults=max(1, min(max_results, 20)))
            .execute()
        )
        results = []
        for ref in resp.get("messages", []):
            msg = (
                self._svc.users()
                .messages()
                .get(
                    userId="me",
                    id=ref["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )
            headers = msg["payload"]["headers"]
            results.append(
                {
                    "id": msg["id"],
                    "from": _header(headers, "From"),
                    "subject": _header(headers, "Subject"),
                    "date": _header(headers, "Date"),
                    "snippet": html.unescape(msg.get("snippet", "")),
                    "unread": "UNREAD" in msg.get("labelIds", []),
                }
            )
        return results

    def read(self, message_id: str) -> dict:
        msg = self._svc.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = msg["payload"]["headers"]
        body = _extract_text(msg["payload"])
        truncated = len(body) > MAX_BODY_CHARS
        return {
            "id": msg["id"],
            "thread_id": msg["threadId"],
            "from": _header(headers, "From"),
            "reply_to": _header(headers, "Reply-To"),
            "to": _header(headers, "To"),
            "subject": _header(headers, "Subject"),
            "date": _header(headers, "Date"),
            "message_id_header": _header(headers, "Message-ID"),
            "body": body[:MAX_BODY_CHARS] + ("\n[Body truncated]" if truncated else ""),
        }

    def send(self, to: str, subject: str, body: str, reply_to_message_id: str | None = None) -> str:
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        request_body: dict = {}
        if reply_to_message_id:
            original = self.read(reply_to_message_id)
            if original["message_id_header"]:
                msg["In-Reply-To"] = original["message_id_header"]
                msg["References"] = original["message_id_header"]
            request_body["threadId"] = original["thread_id"]
        request_body["raw"] = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = self._svc.users().messages().send(userId="me", body=request_body).execute()
        return sent["id"]
