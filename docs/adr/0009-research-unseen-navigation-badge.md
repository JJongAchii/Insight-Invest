# ADR-0009: Research unseen navigation badge

- Status: Accepted
- Date: 2026-09-02
- Owners: `Insight-Invest`

## Context

Web Push announces a new Research item when the PWA is backgrounded, but the in-app navigation had no
durable indication that Research changed. Reusing the unread count would make the navigation permanently
red for older reading backlog and would confuse two different user actions: seeing that new material
arrived and finishing the material.

The indicator must work on the desktop Sidebar and the iPhone bottom navigation, clear when the Research
feed is successfully viewed, and stay consistent between the user's devices.

## Decision

1. Track a separate monotonic `seen_through` watermark in `app/research_seen_state.json`. It does not
   modify canonical Radar records or the independent read and saved states.
2. `GET /research/status` returns the unseen count, current feed generation, and initialization state.
   With no watermark, existing feed items are a baseline and the count is zero; the authenticated client
   explicitly acknowledges that generation once. This avoids presenting the historical feed as new on
   rollout.
3. `PUT /research/seen` accepts the generation actually rendered by the client, caps it at the current
   server generation, and only advances the stored watermark. An item discovered after a stale page was
   loaded therefore remains unseen even if acknowledgment races with a projection refresh.
4. The authenticated application shell polls the compact status every two minutes and on focus or
   reconnect. A successful Research page response acknowledges its generation. The expanded Sidebar and
   iPhone bottom navigation show a red count capped visually at `99+`; the collapsed desktop Sidebar uses
   a red dot while retaining the exact count in its accessible label.
5. Add only `s3:PutObject` access for the new state object. Deployment smoke reads status and verifies the
   status/ack routes without clearing real user state.

## Consequences

- Navigation unseen and library unread answer different questions and can legitimately have different
  counts.
- Acknowledgment is shared between devices. Whichever device views the current Research generation first
  clears the indicator for both.
- The status check adds one small authenticated API request every two minutes while the app is open. It
  reuses the existing Lambda and S3 architecture and adds no always-on resource.
- Timestamp comparison assumes the strongly consistent Radar projection publishes records in discovery
  order. The stored watermark is capped and monotonic, so stale or future client values cannot suppress a
  later generation.

## Verification

- Server tests cover first-run baseline, new-entry counting, stale acknowledgment races, monotonic and
  future-capped watermarks, timezone validation, and static route resolution.
- Client lint and production build validate the shared application-shell query, both navigation variants,
  and Research-page acknowledgment.
- Release verification seeds the initial production watermark to the observed feed generation, confirms
  the existing feed/read/save objects are unchanged, and uses read-only production status smoke.
