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
