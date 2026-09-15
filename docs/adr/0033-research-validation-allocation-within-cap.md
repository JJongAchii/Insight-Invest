# ADR 0033 — Finish source/brief qualification within the existing monthly cap

Date: 2026-09-15. Scope: budget allocation only; selection v10 / boundary v7 unchanged.

The user authorized using the existing budget for proper verification. ADR 0028
already permits reallocating within the $2 total, but not increasing that total.
The separate question about $5 has NOT been approved and is not applied here.

After five fixed bundles, qualification reserved usage is $0.93376520. Production
usage read directly from its independent S3 ledger remains $0.846975. Move $0.10
of unused production allowance to validation: production $0.90 + qualification
$1.10 = the SAME $2.00 aggregate cap. This leaves $0.053025 for subsequent live
analysis. Collection, original reading and existing verified caches continue if
paid analysis reaches that cap. It is not an OpenAI-account-wide billing limit.

Apply only the poller's budget environment variable with revision protection;
preserve every other environment value in memory without logging credentials.
Check both actual ledgers fit their new caps and verify the code digest and other
environment values are unchanged. Do not reset ledgers or failed reservations,
seed caches, rewrite the feed, replay notifications or change schedules.

The qualified-source workflow is idle before this change. Match the workflow's
$1.10 cap, its pre-call live-cap check ($0.90), the infra template and the default.
Commit the adjustment code and tests before the one-field operation. Resume the
remaining same-version fixed cases, then inspect actual Korean briefs. A larger
fresh-source evaluation remains subject to the separate budget approval.
