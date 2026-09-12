# Plans information architecture

## Decision

Unify personal routines and AI scheduling under one sidebar destination named
`Kế hoạch` / `Plans`. The destination offers two peer views:

- `Hôm nay & tuần này`: the AI-assisted plan that ranks tasks, respects personal
  protected time and calendar availability, and identifies the next action.
- `Nhịp lặp lại`: scheduled routines that gather, analyse or summarize on a
  repeating cadence.

The two views remain separate operational surfaces because routine configuration
and a one-day/week plan have different input contracts. They are one product
concept—planning across immediate and recurring horizons—not separate sidebar
modules.

## Verification

`npm run lint` and `npm run build` in `client/web-app` pass. Existing warnings
outside this change and the bundle-size advisory remain.
