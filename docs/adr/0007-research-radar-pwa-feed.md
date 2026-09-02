# ADR-0007: Research Radar feed and iPhone PWA delivery

- Status: Accepted
- Date: 2026-09-02
- Owners: `Insight-Invest` (projection, reading state, Web Push), `quant-data` (canonical records and pending queue)

## Context

Research Radar already polls reviewed public sources and stores deterministic JSON records under
`research-radar/public/records/`. Its current Telegram consumer is useful as a transport, but it leaves
the reading list outside Insight-Invest and duplicates an alert surface that Insight-Invest already
operates. Insight-Invest has a Home Screen PWA, VAPID subscriptions, a Service Worker, and per
event/subscription delivery receipts.

The Action Center is an inbox for portfolio actions. An append-only reading stream has different
filtering and retention semantics and would make that inbox noisy. The existing Action poller also runs
only at 09:45 and 20:30 KST, so it cannot provide feed-like Radar delivery.

## Decision

1. Add an authenticated `/research` API and PWA route. The page is a dedicated reading feed; Action
   Center remains unchanged. Cards expose only the Radar envelope: stable entry ID, source, title,
   public excerpt, authors, publication/discovery times, and original URL.
2. Keep Radar record objects as the canonical content. A dedicated Insight poller lists canonical keys,
   compares them with `app/research_feed.json`, downloads only missing objects, removes projection rows
   whose canonical keys were removed, and rewrites the compact projection only when membership changes.
   API requests read this single projection and never download every canonical object.
3. Store only per-entry read state in `app/research_read_state.parquet`. Read state never changes or
   overwrites the canonical Radar envelope.
4. Pin the Radar producer to UTC `:07/:17/...` and add a lightweight Research poller at
   `:02/:12/...`, about five minutes after each producer cycle and away from the existing Action
   poller. It refreshes the projection, reads `research-radar/realtime/pending/`, maps
   those records to medium-severity notification events, and calls the existing Web Push dispatcher.
   A multi-item cycle produces one notification per active device and deep-links to `/research`; a
   single item deep-links to its exact entry.
5. Reuse the existing `(event_id, subscription_id)` delivery receipt. If one device succeeds and another
   has a transient failure, the pending record remains; the next run skips the successful device and
   retries the other. A 404/410 endpoint is disabled and counts as terminal. Pending objects are deleted
   only when every remaining delivery is settled. No active subscription means the feed is refreshed
   without replaying old items when a device subscribes later.
6. Deploy in fail-closed order: deploy and invoke the Insight poller, verify the initial projection and
   existing Web Push configuration, then switch the quant-data Lambda to external-consumer mode. Keep
   Telegram code only as an explicit rollback mode; it has no credentials or runtime call in the final
   external mode.

## Consequences

- The initial projection contains historical records but creates no notification flood because only
  producer-created pending records are eligible for Push.
- Feed/API freshness is bounded by the Research poller schedule; source discovery remains bounded by
  each source's existing 10/30/60-minute cadence.
- The EC2 fallback still updates the feed projection. A source explicitly marked realtime-disabled does
  not create an immediate notification because the fallback collector does not create pending objects.
- No native iOS application, Apple Developer membership, DynamoDB, or always-on server is introduced.
- The projection and read-state files are single-user read-modify-write objects, consistent with the
  rest of Insight-Invest.

## Verification

- Server tests cover projection reconciliation, no-repeat S3 reads, API filters/read state, Push
  batching, partial failure retry, and terminal subscription cleanup.
- Infrastructure tests fix the cron offset, reserved concurrency, log retention, and least-privilege S3
  prefixes.
- Client lint/build verifies the responsive route, navigation, and deep-link query handling.
- Release smoke invokes the Research poller before querying `/research`; Telegram mode changes only
  after the deployed poller and active subscriptions are verified.
