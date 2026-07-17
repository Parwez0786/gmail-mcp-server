"""
Thin wrappers around the Gmail API for each capability the MCP server exposes.
Each function takes an authenticated `service` object (from gmail_auth.get_gmail_service())
and returns plain dicts/strings that are easy to serialize back to Claude.
"""

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _b64encode_message(mime_message) -> dict:
    raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode("utf-8")
    return {"raw": raw}


def _build_message(to, subject, body, cc=None, bcc=None, thread_id=None,
                    in_reply_to=None, references=None):
    msg = MIMEMultipart()
    msg["to"] = to
    msg["subject"] = subject
    if cc:
        msg["cc"] = cc
    if bcc:
        msg["bcc"] = bcc
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.attach(MIMEText(body, "plain"))
    encoded = _b64encode_message(msg)
    if thread_id:
        encoded["threadId"] = thread_id
    return encoded


def _get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _extract_body(payload) -> str:
    """Pull a readable text/plain body out of a Gmail message payload."""
    if payload.get("body", {}).get("data"):
        data = payload["body"]["data"]
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            data = part["body"]["data"]
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

    # Fall back to any nested part (e.g. text/html) if no plain text was found.
    for part in payload.get("parts", []) or []:
        nested = _extract_body(part)
        if nested:
            return nested

    return ""


def summarize_message(service, msg_id: str, full: bool = False) -> dict:
    fmt = "full" if full else "metadata"
    msg = service.users().messages().get(
        userId="me", id=msg_id, format=fmt,
        metadataHeaders=["From", "To", "Subject", "Date"] if not full else None,
    ).execute()

    headers = msg.get("payload", {}).get("headers", [])
    result = {
        "id": msg["id"],
        "threadId": msg.get("threadId"),
        "snippet": msg.get("snippet", ""),
        "from": _get_header(headers, "From"),
        "to": _get_header(headers, "To"),
        "subject": _get_header(headers, "Subject"),
        "date": _get_header(headers, "Date"),
        "labelIds": msg.get("labelIds", []),
    }
    if full:
        result["body"] = _extract_body(msg.get("payload", {}))
        result["messageIdHeader"] = _get_header(headers, "Message-ID")
    return result


def list_messages(service, query: str = "", max_results: int = 10) -> list:
    resp = service.users().messages().list(
        userId="me", q=query or None, maxResults=max_results
    ).execute()
    ids = [m["id"] for m in resp.get("messages", [])]
    return [summarize_message(service, mid, full=False) for mid in ids]


def get_message(service, message_id: str) -> dict:
    return summarize_message(service, message_id, full=True)


def send_message(service, to: str, subject: str, body: str, cc: str = None, bcc: str = None) -> dict:
    encoded = _build_message(to, subject, body, cc=cc, bcc=bcc)
    sent = service.users().messages().send(userId="me", body=encoded).execute()
    return {"id": sent["id"], "threadId": sent.get("threadId"), "status": "sent"}


def create_draft(service, to: str, subject: str, body: str, cc: str = None, bcc: str = None) -> dict:
    encoded = _build_message(to, subject, body, cc=cc, bcc=bcc)
    draft = service.users().drafts().create(userId="me", body={"message": encoded}).execute()
    return {"id": draft["id"], "messageId": draft["message"]["id"], "status": "draft_created"}


def reply_to_message(service, message_id: str, body: str) -> dict:
    original = service.users().messages().get(
        userId="me", id=message_id, format="full",
        metadataHeaders=["From", "Subject", "Message-ID", "References"],
    ).execute()
    headers = original.get("payload", {}).get("headers", [])
    to = _get_header(headers, "From")
    subject = _get_header(headers, "Subject")
    if subject and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    msg_id_header = _get_header(headers, "Message-ID")
    references = _get_header(headers, "References")
    references = f"{references} {msg_id_header}".strip() if references else msg_id_header

    encoded = _build_message(
        to, subject, body,
        thread_id=original.get("threadId"),
        in_reply_to=msg_id_header,
        references=references,
    )
    sent = service.users().messages().send(userId="me", body=encoded).execute()
    return {"id": sent["id"], "threadId": sent.get("threadId"), "status": "replied"}


def modify_labels(service, message_id: str, add: list = None, remove: list = None) -> dict:
    body = {}
    if add:
        body["addLabelIds"] = add
    if remove:
        body["removeLabelIds"] = remove
    service.users().messages().modify(userId="me", id=message_id, body=body).execute()
    return {"id": message_id, "status": "labels_updated", "added": add or [], "removed": remove or []}


def archive_message(service, message_id: str) -> dict:
    return modify_labels(service, message_id, remove=["INBOX"])


def mark_read(service, message_id: str) -> dict:
    return modify_labels(service, message_id, remove=["UNREAD"])


def mark_unread(service, message_id: str) -> dict:
    return modify_labels(service, message_id, add=["UNREAD"])


def delete_message(service, message_id: str) -> dict:
    # Moves to Trash (recoverable) rather than permanently deleting.
    service.users().messages().trash(userId="me", id=message_id).execute()
    return {"id": message_id, "status": "trashed"}


def list_labels(service) -> list:
    resp = service.users().labels().list(userId="me").execute()
    return [{"id": l["id"], "name": l["name"], "type": l.get("type")} for l in resp.get("labels", [])]


def create_label(service, name: str) -> dict:
    label = service.users().labels().create(
        userId="me", body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    ).execute()
    return {"id": label["id"], "name": label["name"], "status": "created"}
