# ADR-0012: Use a guarded Batch funnel before deep research

- Status: Accepted for implementation; paid execution and deployment remain disabled
- Date: 2026-09-03
- Owner: `Insight-Invest`
- Depends on: ADR-0011 and quant workspace ADR-0006

## Context

ADR-0011 preserves every newly eligible core item as an immutable job request, but deliberately has no
model client. Sending every paper directly into the full literature, implementation, and validation
cycle would make cost scale with feed volume and would bypass the existing human curation and PREREG
gates.

The first remote stage therefore needs to be cheap, deterministic around the model boundary, and safe
to exercise without a key. It should reduce a large inbox to descriptive groups that a person can
inspect. It must not declare that a paper passes source appraisal or deserves implementation.

## Decision

### 1. Build an immutable, deterministic triage packet

`module.research_triage.build_triage_packet` validates each ADR-0011 request, sorts it by `job_id`, and
removes only exact duplicates:

- identical input digest;
- the same normalized HTTP URL, including arXiv abstract/PDF/version aliases and tracking parameters.

It does not use fuzzy or model-based deduplication before the paid boundary. The retained rows become
Batch JSONL requests with `job_id` as the unique `custom_id`; a SHA-256 of the exact JSONL bytes is both
the packet ID and the integrity anchor. Rebuilding from the same request set produces the same bytes.

The packet respects OpenAI's 50,000-request and 200 MB input-file ceilings. A larger corpus must be
partitioned by the future single runner instead of silently truncating rows.

### 2. Use Luna for descriptive metadata triage only

Each row targets `/v1/responses` with `gpt-5.6-luna`, `reasoning.effort=none`, `store=false`, no tools,
and strict structured output. The model receives the title, supplied summary, author, publisher, date,
and URL, but it does not browse or claim to have read the linked paper.

The schema extracts relevance, a stable strategy-family taxonomy, asset class, evidence type, expected
implementation complexity, data requirements, mechanism terms, a short Korean summary, and explicit
risk flags. It contains no score, pass, adopt, or backtest decision. Validated results are grouped
deterministically by relevance, primary family, primary asset class, and evidence type. Every group
retains `human_curation_required=true`.

### 3. Reserve a deliberately conservative maximum cost

The 2026-09-03 Batch rates are pinned in code at USD 0.10 per million input tokens and USD 0.60 per
million output tokens for Luna. Cached input is costed as uncached input. Each request reserves at least
32,000 input tokens plus its 700-token output ceiling; therefore 1,000 normal metadata rows reserve at
most about USD 3.62 under these pinned rates even though expected usage is lower.

Before activation, the rates and model availability must be checked again. The estimate is a local
spend circuit breaker, not an invoice prediction.

The UTC-month S3 ledger uses conditional `If-None-Match`/`If-Match` writes. It holds one immutable
reservation per packet and never releases a reservation automatically. This can under-use the monthly
allowance after failures, but cannot create more room through retries. A single external dispatcher is
still required; the collector EC2 does not become that dispatcher.

### 4. Keep four independent paid-execution gates

No API request is made unless all of the following agree:

1. every source request was created as `requested` with billable execution enabled;
2. `RESEARCH_TRIAGE_API_ENABLED` is exactly `true`;
3. a non-empty dedicated `OPENAI_API_KEY` is present;
4. `RESEARCH_MONTHLY_BUDGET_USD` equals the budget frozen into every source request and the new
   reservation fits the month ledger.

The default remains disabled and no budget has a default. Existing `awaiting_activation` requests may
be used to build and inspect a packet but cannot be submitted by changing only the runtime flag.

### 5. Fail closed on an ambiguous remote submission

After reserving budget, the dispatcher conditionally creates one S3 `claim.json`, uploads the JSONL,
creates the OpenAI batch, and conditionally stores `receipt.json`. A replay with a receipt returns that
receipt without another API call. A claim without a receipt is an ambiguous network/crash state and is
not retried automatically; an operator must reconcile it against the OpenAI project before deciding
what to do. Neither the key nor request authorization is written to S3.

Output ingestion rejects unknown, duplicate, missing, incomplete, and failed `custom_id` rows. It binds
accepted classifications back to the original packet and records token usage plus a conservative
Batch-rate cost estimate. The resulting cluster projection is conditionally stored once at
`research-radar/triage/results/<packet-sha256>/projection.json`; a replay is accepted only when its
canonical bytes are identical.

## Consequences

- Feed volume pays the lowest-cost model stage once per exact paper instead of launching full research
  per item.
- Similar outputs are shown as inspectable groups, while source appraisal, the weekly deep-reading
  budget, PREREG, implementation, and result judges remain unchanged.
- Batch turnaround can be up to 24 hours. Research Radar discovery and iPhone notification remain
  near-real-time; the analysis annotation is asynchronous.
- The current change provides the tested packet, API adapter, result projection, and spend guard. It
  does not schedule a cloud runner, create a key, activate a budget, call OpenAI, or deploy production.

## Activation and rollback

Activation is a later, separately approved operation:

1. merge ADR-0011's handoff before this stacked change;
2. create a dedicated OpenAI project/service-account key outside Git and S3;
3. approve one explicit monthly cap and inject the key and flags into the one-shot runner;
4. perform one small shadow batch, compare reserved and observed usage, then wire the dispatcher;
5. keep full-paper reading and strategy execution behind the existing Insight curation and PREREG
   approvals.

Rollback sets both automation flags to `false`. Existing requests, claims, receipts, and budget ledgers
remain for audit and no new paid submission can begin.

## Verification

- deterministic packet bytes and arXiv/URL exact deduplication;
- strict Responses request shape and output validation;
- all disabled/missing/mismatched authorization combinations stop before S3 writes or API calls;
- S3 monthly reservation blocks cumulative spend before the API boundary;
- successful submission replay makes zero additional remote calls;
- shuffled Batch output produces the same clusters, while missing/duplicate rows fail closed.

## References

- [OpenAI Batch API guide](https://developers.openai.com/api/docs/guides/batch)
- [OpenAI Batch create reference](https://developers.openai.com/api/reference/resources/batches/methods/create)
- [OpenAI GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)
