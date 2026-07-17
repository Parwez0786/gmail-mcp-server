"""
Gmail MCP Server (Python)

Exposes Gmail actions (list, search, read, send, draft, reply, archive,
mark read/unread, delete, labels) as MCP tools that Claude Desktop can call.

Run directly for local testing:
    python server.py
Claude Desktop launches it the same way, configured via claude_desktop_config.json.
"""

import asyncio
import json
import logging

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

import gmail_tools
from gmail_auth import get_gmail_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gmail-mcp-server")

server = Server("gmail-mcp-server")

# Lazily created on first tool call so importing this module never triggers
# an OAuth browser popup by itself.
_service = None


def _get_service():
    global _service
    if _service is None:
        _service = get_gmail_service()
    return _service


TOOLS = [
    types.Tool(
        name="list_emails",
        description="List recent emails, optionally filtered with a Gmail search query.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search syntax, e.g. 'is:unread', 'from:amazon.com'. Empty for most recent."},
                "max_results": {"type": "integer", "description": "Max number of emails to return.", "default": 10},
            },
        },
    ),
    types.Tool(
        name="search_emails",
        description="Search emails using Gmail's search syntax (from:, subject:, after:, has:attachment, etc).",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query."},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="get_email",
        description="Get the full content (including body) of a single email by its message ID.",
        inputSchema={
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    ),
    types.Tool(
        name="send_email",
        description="Send a new email immediately.",
        inputSchema={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "string"},
                "bcc": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    ),
    types.Tool(
        name="create_draft",
        description="Create a draft email without sending it.",
        inputSchema={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "string"},
                "bcc": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    ),
    types.Tool(
        name="reply_to_email",
        description="Reply to an existing email thread by message ID, preserving subject and threading.",
        inputSchema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["message_id", "body"],
        },
    ),
    types.Tool(
        name="archive_email",
        description="Archive an email (remove it from the inbox).",
        inputSchema={
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    ),
    types.Tool(
        name="mark_read",
        description="Mark an email as read.",
        inputSchema={
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    ),
    types.Tool(
        name="mark_unread",
        description="Mark an email as unread.",
        inputSchema={
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    ),
    types.Tool(
        name="delete_email",
        description="Move an email to Trash.",
        inputSchema={
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    ),
    types.Tool(
        name="list_labels",
        description="List all Gmail labels in the account.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="create_label",
        description="Create a new Gmail label.",
        inputSchema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    arguments = arguments or {}
    try:
        service = _get_service()

        if name == "list_emails":
            result = gmail_tools.list_messages(
                service, query=arguments.get("query", ""), max_results=arguments.get("max_results", 10)
            )
        elif name == "search_emails":
            result = gmail_tools.list_messages(
                service, query=arguments["query"], max_results=arguments.get("max_results", 10)
            )
        elif name == "get_email":
            result = gmail_tools.get_message(service, arguments["message_id"])
        elif name == "send_email":
            result = gmail_tools.send_message(
                service, arguments["to"], arguments["subject"], arguments["body"],
                cc=arguments.get("cc"), bcc=arguments.get("bcc"),
            )
        elif name == "create_draft":
            result = gmail_tools.create_draft(
                service, arguments["to"], arguments["subject"], arguments["body"],
                cc=arguments.get("cc"), bcc=arguments.get("bcc"),
            )
        elif name == "reply_to_email":
            result = gmail_tools.reply_to_message(service, arguments["message_id"], arguments["body"])
        elif name == "archive_email":
            result = gmail_tools.archive_message(service, arguments["message_id"])
        elif name == "mark_read":
            result = gmail_tools.mark_read(service, arguments["message_id"])
        elif name == "mark_unread":
            result = gmail_tools.mark_unread(service, arguments["message_id"])
        elif name == "delete_email":
            result = gmail_tools.delete_message(service, arguments["message_id"])
        elif name == "list_labels":
            result = gmail_tools.list_labels(service)
        elif name == "create_label":
            result = gmail_tools.create_label(service, arguments["name"])
        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.exception("Tool call failed: %s", name)
        return [types.TextContent(type="text", text=f"Error running {name}: {e}")]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="gmail-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
