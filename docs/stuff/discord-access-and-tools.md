# Discord access and tool contract

Discord content is imported by the separate crawl pipeline. OAuth does not
fetch messages; it supplies the stable Discord snowflake used to map an app
user to crawled `source_items.author_external_id` values.

## Access levels

| Level | Discord OAuth connection | Author ID found in crawl | Program scopes | Program calendar |
| --- | --- | --- | --- | --- |
| A | yes | yes | all imported Discord program scopes | yes |
| B | yes | no | none | no |
| C | no | not applicable | none; personal Gmail/Jira/Calendar only | no |

The program calendar column covers `program_schedule` (ADR-008), which reads the
organiser's imported schedule rather than Discord, and the
`/calendar/program-sync/*` endpoints (ADR-009), which copy that schedule into the
user's own Google Calendar after they approve an explicit list of entries. Both
are gated on the same level because it is the same body of program data arriving
through a different pipe.

Classification is reconciled after OAuth, on login/refresh/source listing,
before agent scope is applied, after every Discord crawl import, and at backend
startup. This makes old accounts self-healing and upgrades B to A when a later
crawl first observes the member.

## Agent tools

- `discord_search_program(query, since, until)` searches mixed-author program
  discussion chunks within the user's granted channels.
- `discord_search_my_messages(query, since, until)` returns exact
  `source_items` written by the authenticated Discord author. An empty query
  returns the latest messages.
- `discord_get_my_activity(since, until)` counts that author's exact messages
  by channel.
- `discord_list_announcements(query, since, until, limit)` lists program
  announcements newest-first inside the user's granted channels. Level B and C
  get an explicit "no program channels granted" answer rather than an empty
  list, so a level-B user is never told the program has announced nothing.
- `program_schedule(query, since, until, limit)` reads the organiser's schedule
  imported from their ICS feed: workshops, office hours, daily/weekly deadlines,
  gates. Level B and C get an explicit refusal for the same reason as above.
  Group-only entries (mentor duty) are stored with `visibility = "team"` and are
  never returned by this tool — see ADR-008 §4. The access level and cohort are
  request context set by the backend and are absent from the tool schema.

## Announcement filtering

Announcements are derived at query time from `source_items`, not stored in a
separate table, and never inferred by an LLM. `src/services/discord_announcements.py`
scores each message on explicit signals — posted in an announcement channel
(Discord kind 5 or a channel name meaning "thông báo"), broadcast with
`@everyone`/`@here`, sent by an author holding an operating role, containing
announcement keywords, carrying an attachment — and returns the reasons with
each hit so a reader can check the call. A strong signal alone clears the
threshold; weak signals must stack. Role is evidence only, never authority
(BR-04).

It reads `source_items` rather than `chunks` on purpose: the chunker drops bot
messages and very short messages, and announcements are frequently both.

Known limits, measured against the crawled corpus:

- Anyone who can use `@everyone` clears the threshold, including a student
  broadcasting in a discussion channel. The result carries the author name and
  the reasons, so the caller can qualify it; the filter does not claim the
  message is official.
- Messages whose text is empty or only a mention are dropped even in an
  announcement channel — bots post embeds, and `source_items` stores no embed
  body, so there is nothing to hand to the agent. Ones with an attachment are
  kept because the deep link still leads somewhere.

The author snowflake and `scope_ids` are request context set by the backend.
They are deliberately absent from every tool schema, so neither the model nor
prompt text can select another user's identity or expand channel access.
