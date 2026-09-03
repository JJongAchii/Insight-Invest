# ADR-0011: Preserve new core research as an idempotent cloud job request

- Status: Accepted with billable execution disabled
- Date: 2026-09-03
- Owner: `Insight-Invest`
- Depends on: ADR-0010 and quant workspace ADR-0006

## Context

Research Radar already projects canonical records and sends Web Push for newly eligible core items. The
next research phases still depend on a Mac session, so a notification can be delivered without leaving a
durable request for later analysis. Directly invoking a model from the poller would couple collection,
notification, research reliability, and unbounded spend.

The pending record can be retried when push delivery fails. Any handoff therefore also needs an atomic
deduplication boundary; a read-before-write check alone is not safe under concurrent retries.

## Decision

1. Before push delivery, the research poller creates
   `s3://<bucket>/research-radar/jobs/<entry_id>/request.json` with `If-None-Match: *`.
2. Only a record with `research_lane=core` and `notification_eligible=true` can create a request. The
   request snapshots the canonical source fields and binds them to a SHA-256 digest.
3. A conditional-write conflict is a successful replay only when the stored input digest matches. A
   different payload for the same entry fails closed.
4. `RESEARCH_AUTOMATION_ENABLED` accepts only the literal strings `true` or `false` and defaults to
   `false`. A `true` value without `RESEARCH_MONTHLY_BUDGET_USD` fails closed. Disabled requests use
   `awaiting_activation`; no dispatcher, model client, API key, or paid runner is present in this slice.
5. The pending object is not pushed or deleted if request creation fails. This preserves retryability.
6. The authenticated API exposes `GET /research/jobs/{entry_id}` for status inspection. It has read-only
   access to immutable request objects; the poller can only read and conditionally create request objects.
7. Production deploys explicitly pass `ResearchAutomationEnabled=false`. Changing the CloudFormation
   default or manually retaining a previous `true` value cannot silently enable paid execution.

## Consequences

- Turning off the Mac no longer loses the intent to research a new core item.
- Replayed pending records cannot create a second job or a second downstream charge.
- Notifications are slightly more fail-closed: a job-store outage prevents settlement and is retried.
- This slice does not yet analyze papers. Runner credentials, a monthly cap, dispatch, append-only events,
  and the human curation UI remain activation work requiring explicit user approval.

## Verification

- Unit tests cover core-only creation, immutable replay, digest mismatch, default-off configuration,
  handoff failure settlement, and the status route.
- Static infrastructure tests cover the narrow S3 prefix and the explicit disabled deployment value.
