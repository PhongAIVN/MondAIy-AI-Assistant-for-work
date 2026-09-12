# Gmail AnythingLLM bridge

The app keeps the existing Gmail OAuth search/read/deadline sweep and can add
an optional read-only AnythingLLM-compatible Gmail Agent bridge as a second
source. The bridge is disabled by default.

Configure the Apps Script deployment URL, API key, and the one authenticated
application user allowed to use it with the `ANYTHINGLLM_GMAIL_BRIDGE_*`
environment variables in `.env`. Never put the API key in a prompt or tool
argument.

For a request such as `deadline tháng 8`, the bridge creates complementary
Gmail queries:

- a sent-date query for August;
- a wider historical query (180 days before the requested window) containing
  deadline/action/month terms;
- an additional month-term query when a month is explicit.

This catches an email sent in May whose body says the deadline is in August.
Results are thread summaries with `anythingllm_gmail_bridge` provenance. The
agent must read a selected thread before treating it as verified evidence.

The integration intentionally uses only the bridge's read actions (`search`
and `read_thread`). It does not expose send, draft, archive, label, or delete
actions.
