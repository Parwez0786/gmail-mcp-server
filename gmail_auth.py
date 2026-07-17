"""
Handles Google OAuth for the Gmail MCP server.

On first run, this opens a browser window so the user can log in and
approve access. After that, a refresh token is cached in token.json so
future runs don't require a browser at all.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Full read/write access (search, read, send, draft, label, delete, archive).
# Narrow this to ["https://www.googleapis.com/auth/gmail.send"] if you only
# ever want Claude to be able to send mail.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.environ.get(
    "GMAIL_CREDENTIALS_PATH", os.path.join(BASE_DIR, "credentials.json")
)
TOKEN_PATH = os.environ.get("GMAIL_TOKEN_PATH", os.path.join(BASE_DIR, "token.json"))


def get_credentials() -> Credentials:
    """Load cached credentials, refreshing or running the OAuth flow as needed."""
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
        return creds

    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"Missing {CREDENTIALS_PATH}. Download OAuth client credentials from "
            "Google Cloud Console (APIs & Services > Credentials) and save them there, "
            "or set GMAIL_CREDENTIALS_PATH to point at the file."
        )

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    # Opens a local browser tab for the Google login/consent screen.
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    return creds


def _save_token(creds: Credentials) -> None:
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())


def get_gmail_service():
    """Return an authenticated Gmail API client."""
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)
