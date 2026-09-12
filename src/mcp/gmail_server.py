"""Portable, read-only Gmail MCP server for mondAIy.

Run locally with:
    python -m src.mcp.gmail_server

The server uses the existing encrypted per-user OAuth connection. Set
MCP_USER_ID for a single-user local process, or put this server behind an
authenticated MCP gateway that supplies an isolated process per user.
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from src.connectors.base import Source
from src.connectors.gmail import GmailConnector
from src.db import SessionLocal
from src.models.connection import Connection
from src.services.connections import preferred_connection

mcp = FastMCP(
    "mondAIy Gmail",
    instructions=(
        "Read-only Gmail evidence server. Search first, then read only shortlisted messages or threads. "
        "Never send, archive, delete, label, or modify email from these tools."
    ),
    json_response=True,
)


def _connection(db) -> Connection:
    user_id = os.environ.get("MCP_USER_ID", "").strip()
    if not user_id:
        raise RuntimeError("MCP_USER_ID is required for the local Gmail MCP server.")
    row = preferred_connection(db, user_id, "google")
    if row is None:
        raise RuntimeError("No Gmail OAuth connection exists for MCP_USER_ID.")
    return row


async def _list_message_ids(connector: GmailConnector, query: str, max_results: int) -> list[str]:
    token = await connector._access_token()
    import httpx

    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=20) as client:
        page = await connector._get(
            client,
            "/messages",
            params={"q": query, "maxResults": min(max(1, max_results), 100)},
        )
    return [str(item["id"]) for item in page.get("messages", [])]


@mcp.tool()
async def gmail_search_emails(query: str, max_results: int = 20) -> dict:
    """Search Gmail and return metadata/snippets for shortlisted messages."""
    db = SessionLocal()
    try:
        connection = _connection(db)
        connector = GmailConnector(connection, db)
        ids = await _list_message_ids(connector, query, max_results)
        import httpx

        token = await connector._access_token()
        results = []
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=20) as client:
            for message_id in ids:
                results.append(
                    await connector._get(
                        client,
                        f"/messages/{message_id}",
                        params={
                            "format": "metadata",
                            "metadataHeaders": ["From", "To", "Cc", "Subject", "Date"],
                        },
                    )
                )
        return {"tool": "gmail_search_emails", "query": query, "messages": results}
    finally:
        db.close()


@mcp.tool()
async def gmail_read_email(message_id: str) -> dict:
    """Read one exact Gmail message after search returned its message_id."""
    db = SessionLocal()
    try:
        connection = _connection(db)
        connector = GmailConnector(connection, db)
        import httpx

        token = await connector._access_token()
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=20) as client:
            raw = await connector._get(client, f"/messages/{message_id}", params={"format": "full"})
        normalized = connector.normalize(raw, Source(id="INBOX", name="INBOX"))
        return {
            "tool": "gmail_read_email",
            "message_id": message_id,
            "evidence": {
                "subject": normalized.get("subject"),
                "from": normalized.get("author_id"),
                "to": normalized.get("to"),
                "text": normalized.get("normalized_text"),
                "thread_id": normalized.get("thread_id"),
                "source_url": normalized.get("deep_link"),
            },
        }
    finally:
        db.close()


@mcp.tool()
async def gmail_read_email_thread(thread_id: str, max_messages: int = 20) -> dict:
    """Read one exact Gmail thread after search returned its thread_id."""
    db = SessionLocal()
    try:
        connection = _connection(db)
        connector = GmailConnector(connection, db)
        import httpx

        token = await connector._access_token()
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=20) as client:
            body = await connector._get(client, f"/threads/{thread_id}", params={"format": "full"})
        messages = []
        for raw in body.get("messages", [])[: max(1, min(max_messages, 100))]:
            normalized = connector.normalize(raw, Source(id="INBOX", name="INBOX"))
            messages.append(
                {
                    "message_id": normalized.get("id"),
                    "text": normalized.get("normalized_text"),
                    "source_url": normalized.get("deep_link"),
                }
            )
        return {"tool": "gmail_read_email_thread", "thread_id": thread_id, "messages": messages}
    finally:
        db.close()


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
