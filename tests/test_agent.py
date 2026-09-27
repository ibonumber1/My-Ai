"""Offline tests: a fake Claude and a fake Gmail, no network or API keys needed."""

from types import SimpleNamespace as NS

import pytest

from assistant import config
from assistant.agent import Assistant, classify_confirmation


class FakeGmail:
    def __init__(self):
        self.sent = []

    def search(self, query, max_results=5):
        return [{"id": "m1", "from": "Bank <alerts@bank.com>", "subject": "Payment due",
                 "date": "today", "snippet": "Your payment is due", "unread": True}]

    def read(self, message_id):
        return {"id": message_id, "body": "Hello"}

    def send(self, to, subject, body, reply_to_message_id=None):
        self.sent.append((to, subject, body, reply_to_message_id))
        return "sent-1"


def text_block(text):
    return NS(type="text", text=text)


def tool_block(name, args, id_="t1"):
    return NS(type="tool_use", name=name, input=args, id=id_)


class FakeClaude:
    """Replays a scripted list of responses and records each request."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self._responses.pop(0)


def reply(*blocks, stop="end_turn"):
    return NS(content=list(blocks), stop_reason=stop)


DRAFT = {"to": "Jane Doe <jane@example.com>", "subject": "Running late", "body": "Be there at 5."}


def drafting_claude():
    return FakeClaude([
        reply(tool_block("prepare_email", DRAFT), stop="tool_use"),
        reply(text_block("Email to Jane saying you'll be there at 5. Should I send it?")),
    ])


@pytest.mark.parametrize("text,expected", [
    ("Yes", "yes"), ("yes, send it.", "yes"), ("Go ahead", "yes"), ("Don't send it", "no"),
    ("cancel", "no"), ("yes but change it to 6", None), ("what's new", None),
])
def test_classify_confirmation(text, expected):
    assert classify_confirmation(text) == expected


def test_email_is_only_sent_after_yes():
    gmail = FakeGmail()
    bot = Assistant(drafting_claude(), gmail)
    assert "Should I send it?" in bot.handle("Email Jane that I'll be there at 5")
    assert gmail.sent == []
    assert bot.handle("yes") == "Sent to Jane Doe."
    assert gmail.sent == [(DRAFT["to"], DRAFT["subject"], DRAFT["body"], None)]


def test_no_cancels_the_draft():
    gmail = FakeGmail()
    bot = Assistant(drafting_claude(), gmail)
    bot.handle("Email Jane that I'll be there at 5")
    assert bot.handle("no") == "Okay, I won't send it."
    assert gmail.sent == []


def test_draft_expires_after_any_other_reply():
    gmail = FakeGmail()
    claude = drafting_claude()
    claude._responses += [reply(text_block("You have one unread email.")),
                          reply(text_block("Yes to what?"))]
    bot = Assistant(claude, gmail)
    bot.handle("Email Jane that I'll be there at 5")
    bot.handle("actually, any new emails?")
    bot.handle("yes")  # draft is gone, so this goes to Claude and nothing is sent
    assert gmail.sent == []


def test_draft_expires_when_idle():
    gmail = FakeGmail()
    now = [1000.0]
    claude = drafting_claude()
    claude._responses.append(reply(text_block("Yes to what?")))
    bot = Assistant(claude, gmail, clock=lambda: now[0])
    bot.handle("Email Jane that I'll be there at 5")
    now[0] += config.CONVERSATION_IDLE_SECONDS + 1
    assert bot.handle("yes") == "Yes to what?"
    assert gmail.sent == []


def test_tool_results_are_sent_back_to_claude():
    claude = FakeClaude([
        reply(tool_block("search_emails", {"query": "is:unread"}), stop="tool_use"),
        reply(text_block("One unread email from your bank about a payment.")),
    ])
    bot = Assistant(claude, FakeGmail())
    assert bot.handle("Any new emails?") == "One unread email from your bank about a payment."
    tool_result = claude.requests[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and "Payment due" in tool_result["content"]
    assert claude.requests[0]["fallbacks"] == "default"


def test_refusal_gives_short_spoken_reply():
    bot = Assistant(FakeClaude([reply(stop="refusal")]), FakeGmail())
    assert bot.handle("something") == "Sorry, I can't help with that one."
