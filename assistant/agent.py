"""The voice assistant: turns one spoken request into one short spoken answer.

Safety rule enforced in code, not left to the model: an email is only sent
when the user's very next utterance is a plain "yes" after the assistant
read the draft back. Claude can prepare a draft but has no tool that sends.
"""

import json
import re
import time
from dataclasses import dataclass, field

import anthropic

from . import config

SYSTEM_PROMPT = """\
You are a hands-free email assistant. The user is DRIVING and hears your \
replies through text-to-speech, so:

- Reply in one to three short, plain spoken sentences. No markdown, bullet \
symbols, emoji, URLs, or email addresses read out in full unless asked.
- Summarize emails; never read a long body word for word unless the user asks.
- When listing emails, give at most three, most important first, and say how \
many others there are.
- Watch for scams and phishing: urgent payment or gift-card requests, \
password or account "verification", mismatched sender names and addresses, \
unexpected attachments or links, lottery or refund offers. If an email looks \
suspicious, say so plainly first ("Heads up, this looks like a scam") and \
never suggest acting on it.
- To send or reply, call prepare_email. Then read back who it goes to and the \
gist in one sentence, and ask "Should I send it?". You cannot send email \
yourself; the user's "yes" sends it. Never say an email was sent.
- If a request is unclear, ask one short question rather than guessing.

Gmail search tips for search_emails: "is:unread", "newer_than:1d", \
"from:name", "subject:word", "is:important", "in:inbox". Combine them."""

TOOLS = [
    {
        "name": "search_emails",
        "description": "Search the user's Gmail. Returns id, sender, subject, date, snippet and unread flag for each match, newest first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query, e.g. 'is:unread in:inbox newer_than:1d'."},
                "max_results": {"type": "integer", "description": "How many emails to return (1-20).", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_email",
        "description": "Read one email's full text by its id (from search_emails).",
        "input_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    },
    {
        "name": "prepare_email",
        "description": (
            "Prepare an email or reply for the user to approve. This does NOT send it: "
            "after calling this, read the recipient and gist back and ask the user to confirm."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Full email text, written in the user's voice."},
                "reply_to_message_id": {
                    "type": "string",
                    "description": "Id of the email being replied to, so the reply stays in the same thread. Omit for new emails.",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
]

_YES = {"yes", "yeah", "yep", "yup", "send", "send it", "yes send", "yes send it", "yes please",
        "go ahead", "confirm", "confirmed", "do it", "sure", "ok send it", "okay send it"}
_NO = {"no", "nope", "cancel", "cancel it", "dont send", "dont send it", "do not send",
       "stop", "never mind", "nevermind", "no thanks", "scrap it", "delete it"}


def classify_confirmation(text: str) -> str | None:
    """Return "yes", "no", or None. Only exact short phrases count, so
    "yes but change the time" is treated as a new instruction, not a yes."""
    normalized = re.sub(r"[^a-z ]", "", text.lower().replace("'", "")).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if normalized in _YES:
        return "yes"
    if normalized in _NO:
        return "no"
    return None


@dataclass
class PendingEmail:
    to: str
    subject: str
    body: str
    reply_to_message_id: str | None = None


@dataclass
class Conversation:
    messages: list = field(default_factory=list)
    pending: PendingEmail | None = None
    last_active: float = 0.0


class Assistant:
    MAX_TOOL_ROUNDS = 8
    MAX_HISTORY_MESSAGES = 40

    def __init__(self, claude: anthropic.Anthropic, gmail, clock=time.time):
        self._claude = claude
        self._gmail = gmail
        self._clock = clock
        self._convo = Conversation()

    def handle(self, text: str) -> str:
        """Process one spoken request and return the sentence(s) to speak."""
        text = text.strip()
        if not text:
            return "Sorry, I didn't catch that."

        now = self._clock()
        if now - self._convo.last_active > config.CONVERSATION_IDLE_SECONDS:
            self._convo = Conversation()  # also drops any stale draft
        self._convo.last_active = now

        # Confirmation is decided here, in code, before Claude sees anything.
        pending = self._convo.pending
        self._convo.pending = None  # a draft is valid for exactly one reply
        if pending:
            answer = classify_confirmation(text)
            if answer == "yes":
                try:
                    self._gmail.send(pending.to, pending.subject, pending.body,
                                     pending.reply_to_message_id)
                except Exception:
                    return self._note(text, "Sorry, sending failed. The email was not sent.")
                return self._note(text, f"Sent to {_display_name(pending.to)}.")
            if answer == "no":
                return self._note(text, "Okay, I won't send it.")

        if len(self._convo.messages) > self.MAX_HISTORY_MESSAGES:
            self._convo = Conversation(last_active=now)

        try:
            return self._ask_claude(text)
        except anthropic.APIError:
            self._convo = Conversation(last_active=now)  # history may be half-written
            return "Sorry, I couldn't reach the assistant. Please try again."

    def _note(self, user_text: str, reply: str) -> str:
        """Record a turn that code answered, so Claude keeps the context."""
        self._convo.messages.append({"role": "user", "content": user_text})
        self._convo.messages.append({"role": "assistant", "content": reply})
        return reply

    def _ask_claude(self, text: str) -> str:
        messages = self._convo.messages
        messages.append({"role": "user", "content": text})

        for _ in range(self.MAX_TOOL_ROUNDS):
            response = self._claude.beta.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": config.CLAUDE_EFFORT},
                # If a safety filter declines, retry on a suitable model automatically.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "refusal":
                return "Sorry, I can't help with that one."
            if response.stop_reason != "tool_use":
                return _spoken_text(response.content) or "Done."

            results = []
            for block in response.content:
                if block.type == "tool_use":
                    content, is_error = self._run_tool(block.name, block.input)
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                        "is_error": is_error,
                    })
            messages.append({"role": "user", "content": results})

        self._convo = Conversation(last_active=self._convo.last_active)
        return "Sorry, that took too many steps. Try asking a simpler way."

    def _run_tool(self, name: str, args: dict) -> tuple[str, bool]:
        try:
            if name == "search_emails":
                found = self._gmail.search(args["query"], int(args.get("max_results", 5)))
                return json.dumps(found) if found else "No emails matched.", False
            if name == "read_email":
                return json.dumps(self._gmail.read(args["message_id"])), False
            if name == "prepare_email":
                self._convo.pending = PendingEmail(
                    to=args["to"],
                    subject=args["subject"],
                    body=args["body"],
                    reply_to_message_id=args.get("reply_to_message_id"),
                )
                return ("Draft saved, NOT sent. Read the recipient and gist back in one "
                        "sentence and ask the user to confirm."), False
            return f"Unknown tool: {name}", True
        except Exception as exc:  # report tool failures to Claude rather than crashing
            return f"{type(exc).__name__}: {exc}", True


def _spoken_text(content) -> str:
    return " ".join(b.text for b in content if b.type == "text").strip()


def _display_name(address: str) -> str:
    """'Jane Doe <jane@x.com>' -> 'Jane Doe'; 'jane@x.com' -> 'jane'."""
    if "<" in address:
        name = address.split("<")[0].strip().strip('"')
        if name:
            return name
        address = address.split("<")[1].rstrip(">")
    return address.split("@")[0]
