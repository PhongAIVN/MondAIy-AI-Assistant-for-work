# Query task-import tool

## Objective

Move file and Google-document task extraction to the chat composer so users can
choose a source, submit it without composing a prompt, and review the same task
proposals in place.

## Scope and behaviour

- The `Nhập task` composer tool presents exactly two source choices: local file
  or a Google link.
- Local input accepts at most five `.xlsx`/`.docx` files, each at most 200 KB.
  The client rejects invalid files before upload; the existing API independently
  enforces the same limit and does not retain uploaded content.
- Google input accepts a Google Docs or Google Sheets URL and invokes the
  existing read-only extraction APIs. It does not open a free-form chat prompt.
- Proposals use the existing confirmation path; no task is silently created.

## Verification

- `npm run lint` in `client/web-app`: pass with pre-existing warnings outside
  this tool.
- `npm run build` in `client/web-app`: pass; existing bundle-size advisory only.
