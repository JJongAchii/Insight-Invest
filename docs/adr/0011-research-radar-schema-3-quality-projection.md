# ADR-0011: Research Library는 schema 3 품질 계약만 알림 가능하게 투영한다

- Status: Accepted
- Date: 2026-09-04
- Owner: `Insight-Invest`
- Depends on: `quant-data` ADR-0017

## Context

Schema 1과 2의 기존 record에는 본문 provenance, evidence excerpt, source digest, maintainer
resolution을 함께 검증할 계약이 없다. 이전 projection의 `core` 또는 pending flag를 그대로
신뢰하면 producer를 엄격하게 바꾼 뒤에도 오래된 항목이 sidebar badge와 iPhone Web Push에
남는다.

## Decision

1. Continue accepting record schemas 1, 2, and 3. Always project schemas 1/2 as
   `archive`/`context` with `notification_eligible=false`, regardless of their historical lane fields.
2. Validate schema 3 fail-closed: lowercase SHA-256 source digest; known provenance and resolution;
   bounded, dimension-aligned excerpts; method plus secondary evidence when the evidence gate is true;
   at least two semantically distinct topic terms (singular/plural and punctuation aliases count once);
   and internally consistent lane, core gates, and notification fields.
3. Preserve schema-3 fields through `research_feed.json` and the existing Research API. The client shows
   a compact chain-of-custody strip for evidence-update type, provenance, and each evidence dimension.
4. Keep the existing core/discovery/all, read/unread/saved, search, deep-link, and mark-all-read behavior.
   Update lane copy to describe the strict gates; do not create a new route or navigation concept.
5. Drive unseen count and push only from validated `notification_eligible`. Legacy pending records are
   suppressed and deleted through the existing per-item settlement path. Read, saved, and seen storage
   is not reset or migrated.

## Consequences

- Historical cards remain queryable under 전체 기록 while they can no longer create badges or push.
- Malformed schema-3 data stops projection instead of being silently downgraded to an alertable item.
- The projection container remains schema 1; `record_schema_version` records each item's canonical
  contract version without changing library-state keys.

## Verification

- Server tests cover schema-1/2 demotion, schema-3 field survival, malformed digest/evidence/resolution,
  pending suppression, API projection, and byte-for-byte preservation of read/saved/seen state.
- Client ESLint and Next.js production build check the additive TypeScript and badge rendering contract.
- A producer-consumer fixture must carry one schema-3 item from qdata output through projection while
  a malformed schema-3 record and legacy notification record fail closed.
