# ADR 0032 — Preserve the context required by literal research evidence

Date: 2026-09-15. Status: implemented; actual-source qualification required.

## Observed failure

Run 34846012193 (app 9cc0d8e, selector v8 / boundary v6) performed six
successful calls on the unchanged positive trio. D.E.Shaw and CFM were retained;
Robeco systematic credit was held. The selector chose a list of characteristics
and an undefined ranking-engine description instead of the explanatory credit
comparison. The checker correctly refused those weak proposals. This is a real
false negative for the original, not permission to change its frozen label.
Cost: $0.02061700. Qualification ledger: $0.82300920 of $1. No other v8 panel
cases were run. No production code, feed or classification cache was changed.

Inspection of the exact parsed original confirmed both adjacent passages are
citable: a generic wide-spread value screen, followed by comparison with the
issuer's fundamental risk, rating and maturity. The old schema permitted only
ONE sentence for each evidence field. It could not transmit this baseline and
correction together. Other numerical examples likewise omitted the measured
quantity or the condition defined immediately before them. This is an input
contract defect, not proof that a more expensive model is required.

## Decision

Selector v9 may select 1–4 consecutive original sentences, up to 1,200 total
characters, per insight, purpose or reading point. Literal order, adjacency,
citable status and length are checked in code. Gapped, reordered, duplicated,
context-only and oversized spans fail closed. Duplicate sentences elsewhere in
the source are resolved by the whole adjacent span, not isolated text lookup.

Boundary v7 still receives only these bounded proposals, without title,
publisher, source body or first-reader labels. It judges the object of the
proposed analysis, not an unseen document. A numerical comparison must identify
its outcome; the checker may not supply a missing metric from memory. There is
no new paid stage, model change, source blacklist, reproducibility requirement,
score or budget increase. The writer and immutable cache publisher resolve the
same exact spans; version fingerprints prevent reuse of old selector decisions.

## Frozen validation before API calls

Keep all 18 original labels and hashes from ADR 0031: 10 core / 8 non-core.
They are a development regression panel, NOT a pristine unseen holdout. The
known examples informed the repair; report that limitation rather than an
accuracy claim. First rerun the positive trio and inspect the actual selected
spans and accepted roles. A correct label on a weak premise is still a failure.
Then run the remaining fixed bundles with the same versions; do not cherry-pick
receipts from earlier versions. Keep every earlier failure and its costs.

The remaining qualification budget is $0.17699080. Existing $1 production + $1
qualification monthly caps remain; failed reservations are not reset. Read-only
qualification does not publish feed cards or replay notifications. Release still
requires source-semantic inspection, producer/consumer tests, UI/build checks and
preservation of existing read/saved/seen/delivery state.

## First API call exposed a mechanical contract failure

Run 34906845443 / app 957102b stopped after its first v9 selector call because
one selected span exceeded 1,200 characters. No v9 selection receipt was accepted;
the report retained old v8/v6 decisions, explicitly pending under the current
version. They must NOT be read as new successful or failed semantic outcomes.
The failed reservation $0.02031075 remains; the ledger is now $0.84331995.

The technical repair v10 precomputes every valid 1–4 sentence span and exposes
allowed end IDs alongside each original passage. The strict provider schema
accepts only exact START:END choices through a shared `$defs` string pattern.
The adapter resolves the choice back into the existing literal passage contract;
it never clips an oversized proposal. A pattern, rather than a capped enum list,
preserves full bounded-source coverage for longer originals. The documented
[Structured Outputs pattern and definition support](https://developers.openai.com/api/docs/guides/structured-outputs)
was checked before implementation. Code still validates the response itself.

No boundary semantic rule or fixed original expectation changed. First repeat the
positive trio with v10/v7, then the same 18-original panel. No automatic retry of
the failed v9 code, reservation refund, model upgrade or production write.

## Actual v10 positive trio and downstream handoff

Run 34909761737 / app f104e03 completed all six calls. All three originals are
core. D.E.Shaw now transmits the correlated-index example's initial allocation,
changed volatility estimate and resulting allocation together. Robeco's accepted
insight is the spread-versus-issuer-risk/rating/maturity comparison, not its ranking
engine. The latter was explicitly objective_or_profile. CFM transmits the
regression and residual explanation. These are source-reading decisions, not
validation of the authors' performance claims. Cost $0.02896950; ledger
$0.87228945. Remaining fixed negative/positive cases are still required.

Inspection also showed a producer/consumer defect: the selected insight admitted
the original, but the writer's separate why_read could omit it entirely; its
method_data could still contain the rejected ranking-engine blurb. The writer
now uses the boundary-accepted insight (or accepted method when that is the only
contribution) for why_read, and suppresses a method proposal whose evidence role
was rejected. Question/finding/limitation retain literal source selection and
the existing per-field factual review. Original selector/checker receipts are not
edited. Cache identity follows the actual effective reading plan, so only changed
inputs invalidate drafts. This does not change the v10/v7 document gate or its
frozen labels and adds no model calls/stages.

An offline duplicated-sentence test also reproduced a cache publication defect:
the publisher selected a same-text citation outside the checker's visible span.
It now reconstructs the object citation only from the actually visible proposal
IDs. The regression initially failed and passes with that repair; publication
still re-fetches exact source content and never overwrites existing cache objects.
