"""One-time Gmail sign-in. Opens a browser, then saves token.json.

Usage:  python scripts/authorize_gmail.py
Needs credentials.json (an OAuth "Desktop app" client from Google Cloud Console)
in the project folder. See docs/setup.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from assistant import config  # noqa: E402


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file(config.GMAIL_CREDENTIALS_FILE, config.GMAIL_SCOPES)
    creds = flow.run_local_server(port=0)
    Path(config.GMAIL_TOKEN_FILE).write_text(creds.to_json())
    print(f"Saved {config.GMAIL_TOKEN_FILE}. Keep it private; it grants access to your Gmail.")


if __name__ == "__main__":
    main()
