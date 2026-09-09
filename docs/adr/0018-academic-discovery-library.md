# ADR-0018: Academic discovery is a library input, not a reviewed research verdict

Date: 2026-09-08
Status: Implemented in working branch; not deployed

Use the existing schema-4 reading feed for bounded topic-discovered papers.
Retain original publisher, DOI, identity aliases, discovery queries/versions,
publication/update/discovery timestamps and actual original-access status.
Search includes publisher, DOI and discovery route in addition to existing
title/author/summary fields. Keep read/save/seen storage unchanged.

`academic-discovery-v1` items are always discovery, `not_requested` and
non-notifiable at both projection and API-read time. Fetching a PDF must not
trigger a paid model call or imply scientific validation. Original subscription
items keep their existing review gate; original discovery works when the LLM
is unavailable or semantically unqualified.

The UI retains its existing design and controls. Show the original publisher
separately from “OpenAlex/arXiv에서 발견”. Use the source abstract as the preview
even when the parser inspected a PDF; display the actual abstract/body access
status and do not promise that a Korean summary is in progress for an item that
has not been queued for one.

Producer alias merging preserves the first entry ID, so no destructive user-state
migration is needed. The producer→consumer regression verifies byte-identical
read/save/seen files after late DOI enrichment. A separate offline assertion
fails if academic intake invokes source re-fetch, summary or source-review calls.

The technical details and rollout limits are in quant-data ADR-0023. This does
not qualify OpenAlex publication quality, validate paper claims, enable automatic
strategy implementation, or resolve the separately pending Korean-review release.
