# ADR-0010: Research Library defaults to an explainable core lane

- Status: Accepted
- Date: 2026-09-03
- Owner: `Insight-Invest`
- Depends on: `quant-data` ADR-0016

## Context

Research Library already preserved read and saved state, search, deep links, Web Push, and an unseen
navigation badge. Its projection nevertheless presented every official-source discovery as equivalent.
The user's main screen and alert channel were therefore dominated by context items even though the
canonical history itself remained useful for later search.

The producer now classifies new records as `core`, `discovery`, or `context` and explicitly marks push
eligibility. Existing schema-1 records have no such fields and must remain accessible without being
silently promoted.

## Decision

1. Normalize schema-1 canonical records and pre-migration projection items to `context`, with
   `notification_eligible=false`. Validate schema-2 quality fields and reject malformed or notifiable
   non-core records.
2. Add an independent `lane` API filter: `core` (default), `discovery`, or `all`. Read-state views,
   source selection, and search operate within the selected lane. Exact entry deep links remain
   authoritative and bypass filters.
3. Return per-lane counts and render three prominent choices: 핵심 연구, 발견함, and 전체 기록.
   Cards show their lane and up to two matched terms so the user can understand why a core item was
   selected.
4. Scope “모두 읽음” to the selected lane. Reading remains reversible, and changing lanes does not
   alter saved or read state.
5. Count only `notification_eligible=true` items for the red unseen badge. Background Web Push likewise
   dispatches only eligible pending records.
6. Treat the pending queue as untrusted input during rollout. Old or non-eligible pending objects are
   removed without delivery; eligible items retain the existing retry and settlement behavior.

## Consequences

- The default screen becomes useful immediately after the five new sources are baselined, while all 409
  historical records remain available under 전체 기록.
- A saved context item is visible when the user selects 전체 기록 and 보관함; lane and library state are
  intentionally separate filters.
- Unseen and unread remain different concepts. Unseen now means “new alert-worthy core research”, while
  unread is the reading backlog in the selected lane.
- The projection format remains schema 1 at the container level for compatibility; quality fields are an
  additive item contract and legacy items are migrated on the next reconciliation.

## Verification

- Server tests cover legacy migration, schema-2 validation, default-core filtering, full-history access,
  per-lane counts, scoped mark-all, unseen behavior, and suppression of old pending noise.
- Client lint and the Next.js production build verify the lane URL/API contract and responsive controls.
- The release smoke requires non-empty preserved history through `lane=all` and validates the default
  core response contract without assuming that a freshly deployed, pre-baseline core lane is non-empty.
- Deployment smoke must preserve the existing read/save objects, return historical items with
  `research_lane=context` under `lane=all`, and deliver a controlled core pending item only once.
