"""Settings loaded from environment variables (and a local .env file)."""

import os

from dotenv import load_dotenv

load_dotenv()

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5")
# Low effort keeps spoken answers fast; raise to "medium" if answers feel shallow.
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "low")
ASSISTANT_TOKEN = os.getenv("ASSISTANT_TOKEN", "")
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", "token.json")
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")

# Read mail and send mail; nothing else (no deleting, no settings changes).
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

# A conversation resets after this many idle seconds, so an old draft or
# topic never carries over into a new drive.
CONVERSATION_IDLE_SECONDS = 10 * 60
