# ADR-0008: Research Library state and discovery

- Status: Accepted
- Date: 2026-09-02
- Owners: `Insight-Invest`

## Context

The first Research Radar screen exposed the full feed and an `unread_only` switch, but the interface
did not make it obvious that read items were retained. It also lacked a durable way to keep important
items and required browsing the feed again to find a known title, author, or topic.

This is a single-user application with a compact projection (currently hundreds, not millions, of
records). The canonical Research Radar envelopes remain owned by `quant-data`; personal library state
must not rewrite those records.

## Decision

1. Present four explicit library views: `all`, `unread`, `read`, and `saved`. Reading is a reversible
   state transition, never deletion. Keep the legacy `unread_only` API parameter and `filter=unread`
   client link compatible while new links use `view`.
2. Extend `app/research_read_state.parquet` with nullable `saved_at`. Keep the existing filename to
   avoid a storage migration. Loading an old two-column file synthesizes the new column, and updating
   either state preserves the other state and its timestamp.
3. Search the compact server projection by title, public summary, author, and source name. Normalize
   Unicode with NFKC, compare case-insensitively, and require every whitespace-delimited search term
   to match. Do not add a search service or index at this scale.
4. Add a confirmed `mark all read` action over the current canonical projection. It only timestamps
   entries that are still unread, preserves existing read timestamps and saved state, and then returns
   the client to `all` so the result does not look deleted.
5. Keep notification deep links authoritative: an exact `entry_id` bypasses view, source, and search
   filters and still opens a read or saved item.

## Consequences

- Read material remains discoverable in `all`, `read`, search results, and—when explicitly kept—in
  `saved`.
- Saved state is independent of read state, so opening a saved item cannot remove it from the library.
- State remains a single-user read-modify-write object. Multi-user accounts or concurrent writers would
  require a different storage contract.
- Folders, tags, notes, semantic search, full-text document ingestion, and LLM summaries are outside
  this slice. They can be added later only if observed library use justifies the extra model and UI.

## Verification

- Server tests cover all four views, field search, legacy-state migration, deep-link precedence,
  independent read/save transitions, and idempotent mark-all behavior with timestamp preservation.
- Client lint and production build verify the responsive library controls and API contracts.
- Deployment smoke verifies the extended response contract without changing the user's real read or
  saved state; global state mutation is exercised against isolated test storage.
