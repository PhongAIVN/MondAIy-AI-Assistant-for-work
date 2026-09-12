# Self-hosted Gmail MCP

`src/mcp/gmail_server.py` packages a portable, read-only Gmail MCP server in
the repository. It is independent of the Codex remote Gmail plugin.

The server exposes:

- `gmail_search_emails`: metadata/snippet shortlist
- `gmail_read_email`: exact message body after search
- `gmail_read_email_thread`: exact thread after search

The intended flow is search first, then read only shortlisted evidence. The
server never sends, archives, deletes, or changes labels.

## Run

Install dependencies:

```powershell
pip install -r requirements.txt
```

Set a user-scoped process environment:

```powershell
$env:MCP_USER_ID="<mondaiy-user-id>"
$env:MCP_TRANSPORT="stdio"
python -m src.mcp.gmail_server
```

For HTTP clients:

```powershell
$env:MCP_TRANSPORT="streamable-http"
python -m src.mcp.gmail_server
```

The process must run behind authentication in multi-user production. Never
accept an arbitrary `user_id` from an untrusted tool caller; isolate the MCP
process or derive the user from the authenticated gateway context.

The existing REST Gmail connector remains the fallback when MCP is unavailable.
