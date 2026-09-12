# Mobile chatbot and sidebar refresh

## Objective

Bring the mobile chatbot closer to the supplied Littlebird-style reference while keeping the P-004 cream palette and exposing the same primary sidebar concepts as the web app.

## Research sources

- `client/web-app/src/components/layout/Sidebar.tsx` — canonical web navigation labels and sidebar sections.
- `client/web-app/src/lib/conversationApi.ts` — server conversation contracts.
- `src/api/conversations.py` — backend conversation list/detail routes.
- `apps/mobile/src/components/RealWorkspace.tsx` — existing mobile workspace/chat behavior.
- `apps/mobile/src/api/client.ts` — mobile API client.
- Base commit: `0d25411fd222a3da6f7dd7a21a567e4f3407cf69`.

## Scope

- Added a mobile hamburger drawer with New chat, Search, Tasks, Routines, Meeting Notes, Sources, conversation history, settings, help, and sign out entries.
- Loaded conversation history/detail through the existing authenticated backend conversation endpoints.
- Refreshed chat presentation with centered mascot, cream canvas, suggestion chips matching web prompts, attachment affordance, Default mode pill, microphone affordance, and circular send action.
- Kept the existing `/api/v1/chat` send path unchanged for runtime stability; create/send conversation client methods are prepared for the next persistence migration.
- Updated the mobile suggestion catalog to the web assistant's eight starter prompts.

## Verification

- `apps/mobile/.\node_modules\.bin\tsc.cmd --noEmit` — passed.
- `node --experimental-strip-types --test tests/**/*.test.ts` — passed, 10 tests.
- `git diff --check` — passed.

## Risks and follow-up

- Routines, Meeting Notes, settings, help, and attachment/microphone affordances are intentionally surfaced as mobile actions/placeholders where a dedicated native screen or native capability is not yet present.
- Existing mobile chat replies remain stateless through `/api/v1/chat`; migrate send/create to `/api/v1/conversations/{id}/messages` in a follow-up once streaming/task-draft parity is covered.
- No backend schema, endpoint, or deploy change was made.
