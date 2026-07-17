# Gmail MCP Server

Local MCP server that lets Claude Desktop read and manage your Gmail (list, search, send, draft, reply, archive, labels, trash).

Claude asks → this server calls the Gmail API → actions run on **your** account.

## Structure

```
gmail-mcp-server/
├── server.py         # MCP tools + dispatch
├── gmail_auth.py     # OAuth + token cache
├── gmail_tools.py    # Gmail API wrappers
├── requirements.txt
├── credentials.json  # from Google (do not commit)
└── token.json        # created after first login (do not commit)
```

## Setup

### 1. Install (Python 3.10+)

```bash
cd gmail-mcp-server
/opt/homebrew/bin/python3.12 -m venv .venv   # or any python3.10+
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Cloud credentials

1. [Google Cloud Console](https://console.cloud.google.com/) → create/select a project.
2. Enable **Gmail API**.
3. **OAuth consent screen** → External → fill app info → add yourself as a **Test user** (keep status **Testing**).
4. **Credentials** → Create → **OAuth client ID** → type **Desktop app** → download JSON.
5. Save it as `credentials.json` in this folder (must have an `"installed"` key, not `"web"`).

### 3. Claude Desktop config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gmail": {
      "command": "/Users/mdparwezansari/Desktop/gmail-mcp-server/.venv/bin/python",
      "args": ["/Users/mdparwezansari/Desktop/gmail-mcp-server/server.py"]
    }
  }
}
```

Use absolute paths. Quit Claude fully (**Cmd+Q**) and reopen.

Claude starts the server automatically — you don’t need to run `python server.py` yourself.

### 4. First OAuth

In Claude, ask e.g. “List my recent emails.” Approve Google in the browser. That creates `token.json` for later runs.

## Tools

| Tool | Description |
|------|-------------|
| `list_emails` | Recent mail (optional Gmail `query`) |
| `search_emails` | Search (`from:`, `is:unread`, etc.) |
| `get_email` | Full body by message ID |
| `send_email` | Send now |
| `create_draft` | Draft only |
| `reply_to_email` | Reply in-thread |
| `archive_email` | Remove from inbox |
| `mark_read` / `mark_unread` | Toggle unread |
| `delete_email` | Move to Trash |
| `list_labels` / `create_label` | Labels |

Scope: `gmail.modify` (change in `gmail_auth.py` if you want less access).

## Optional env

- `GMAIL_CREDENTIALS_PATH` — default `./credentials.json`
- `GMAIL_TOKEN_PATH` — default `./token.json`

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `mcp` won’t install | Need Python 3.10+ |
| Server not connected | Check paths; Cmd+Q Claude and reopen; see `~/Library/Logs/Claude/mcp-server-gmail.log` |
| Access blocked | Add your Gmail as OAuth **Test user** |
| Re-login needed | Delete `token.json` and call a Gmail tool again |

Never commit `credentials.json` or `token.json`.
