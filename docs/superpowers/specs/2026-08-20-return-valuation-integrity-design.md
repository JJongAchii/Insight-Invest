# Return & Valuation Integrity Design

- Status: Phase 1 implemented; exact KR cash-event total return gated
- Date: 2026-08-20
- Scope: Insight-Invest + quant-data ADR-0008

Implementation update (2026-08-20): Factor/Signal next-open execution,
explicit price-series metadata, same-day KR valuation validation, market
coverage, and Data Trust calculation contracts are implemented. The official
KRX ETF snapshot's `FLUC_RT` field also now drives a separately labelled
reference-price-adjusted series. An exact KR cash-event table remains disabled
because a stable official amount/ex-date/revision/delisted-history contract was
not proven; no price/NAV inference is used. The general backtest now records its
actual prior-close/rebalance-close execution contract and rejects mixed return
bases or missing requested assets. A future next-open migration still requires
a common adjusted-open/return contract across every selected market.

## 1. Outcome

Every displayed price, return, valuation multiple, study, and backtest must say
what it measures, when it became knowable, and whether its coverage is complete.
No code path may silently treat price return as total return or use an
after-close signal as if it had been executed at that same close.

The user-facing result is:

- the header always shows a tradable latest close;
- performance cards default to gross total return only when complete event
  coverage exists;
- charts expose `Price` and `Total Return` as distinct views;
- PER/PBR show source date, input basis, and a meaningful missing reason;
- market PER shows the share of names and market cap represented;
- studies and backtests expose signal and execution dates.

Menu and component titles remain English (`Valuation`, `Price Return`, `Total
Return`, `Calculation Basis`, `Coverage`). Explanations and cautions remain in
Korean.

## 2. Confirmed current-state findings

### 2.1 Correct and retained

- KR stock capital-action adjustment reconciles raw close to KRX official daily
  change and is suitable for price-return calculations.
- KR PER/PBR/DIV are KRX-published daily values, not app estimates.
- US app prices combine Massive split-adjusted prices and cash dividends into a
  gross total-return series.
- Current asset search and routing use the qdata/app master, not the former RDS
  data path.

### 2.2 Ambiguous or incomplete

- KR stock `adj_close` excludes cash dividends.
- At design time KR ETF `adj_close` was an alias for raw close. Implementation
  now uses KRX `FLUC_RT` to produce `krx_reference_price_adjusted_return`, while
  deliberately withholding the `Total Return` label until exact cash events
  are available.
- US `adj_close` is actually a total-return pseudo-price anchored to latest
  close, so its meaning differs from KR `adj_close`.
- KR stock detail fetches latest price and valuation independently and does not
  return a valuation as-of date or missing reason.
- Market PER excludes nonpositive PER names but does not expose the resulting
  name/market-cap coverage.
- US PER/PBR are not currently calculated; the US fundamentals card only shows
  SEC annual facts.

### 2.3 Execution-timing defects

`scripts/build_insights.py` currently has two after-close/same-close paths:

1. `factor_returns`: score at close `t`, then uses `P[t+1] / P[t] - 1`.
   The KRX PER and closing price are only complete after close `t`, so entry at
   `P[t]` is not executable.
2. `signal_study`: signals use same-day close, official change, flow, volume,
   and market cap, then measure `P[t+h] / P[t] - 1`. These inputs are also
   complete only after close.

Both artifacts must be treated as research calculations requiring replacement,
not merely relabelled. Their existing performance numbers must not be carried
forward into decisions after the correction.

## 3. Canonical application return contract

### 3.1 Fields

The datastore introduces an explicit versioned response:

```text
ReturnSeriesPoint
  meta_id
  ticker
  trade_date
  close                  # tradable raw close
  price_adj_open         # open * capital-action factor
  price_adj_close        # close * capital-action factor
  distribution_cash      # gross cash on ex-date, original share basis
  price_return
  total_return
  total_return_index

ReturnSeriesMeta
  schema_version
  source
  price_as_of
  event_as_of
  return_basis
  distribution_coverage  # complete | partial | unavailable | stale
  coverage_start
  calculation_version
```

`total_return_index` is a wealth index, not a tradable price. It is rebased to
100 at the requested view boundary by the API/client. `latest_price` always
comes from `close`, even when metrics use total return.

### 3.2 No ambiguous internal defaults

New internal calls use:

```python
read_return_data(..., basis="price")
read_return_data(..., basis="total")
```

`basis` is mandatory. Legacy `read_price_data()` and the existing
`adj_close`/`gross_return` response remain temporarily for compatibility, but
new or migrated code may not call them.

For a multi-asset request:

- `basis="total"` succeeds only if every selected asset has complete coverage
  over the common requested interval;
- otherwise it returns a structured coverage error;
- a caller may explicitly request `basis="price"` for all assets;
- per-asset silent fallback is forbidden because it creates a mixed-basis
  portfolio.

### 3.3 Composition

A common pure module composes both KR and US series:

```text
F_t             = price_adj_close_t / close_t
cash_adjusted_t = distribution_cash_t * F_t
total_return_t  = (price_adj_close_t + cash_adjusted_t)
                  / price_adj_close_(t-1) - 1
```

An open-to-open index applies the same cash event to `price_adj_open`. This is
used only for executable studies. Cash is gross, pre-tax, and reinvested. User
portfolio cash dividends recorded in the ledger remain account cash flows and
must not be added a second time.

## 4. Consumer mapping

| Consumer | Required basis | Reason |
|---|---|---|
| Stock header/latest holding value | `close` | Tradable mark |
| Price chart | `price_adj_close` | Continuous comparable price |
| Total Return chart | `total_return_index` | Dividend-reinvested wealth |
| YTD/3M/1Y, volatility, MDD | `total_return` when complete | Investor experience |
| Limit-up/down, price band, tick size | `close`, `chg_pct` | Exchange rule basis |
| ADV/capacity | `value` | Do not reconstruct from adjusted values |
| 52-week high/momentum | explicit price or total policy | No source-dependent default |
| Factor and signal studies | executable open-to-open total return | After-close signal timing |
| Simulation/backtest/optimization | explicit total return | Cross-asset comparability |
| Holding market value | `close` | Current liquidation mark |
| Actual-account TWR | ledger cash flows + close marks | Avoid dividend double count |
| PER/PBR | same-date KRX valuation snapshot | Source-consistent multiple |

Broad descriptive market breadth can remain price-return based, but the basis is
stored in artifact metadata and displayed in help text.

## 5. Execution-safe research artifacts

### 5.1 Factor Lens v2

For signal date `D`:

1. build scores from data available through `D` close;
2. choose ranks within `D` only;
3. execute at `D+1` open;
4. measure one-day return from `D+1` open to `D+2` open;
5. apply distributions through the open-based total-return index;
6. reject rows with no executable next open instead of forward-filling;
7. record `signal_date`, `entry_date`, `exit_date`, `return_basis`, and
   `calculation_version`.

### 5.2 Signal Study v2

For an event observed at `D` close, horizon `h` measures `D+1` open to the open
`h` trading sessions later. The benchmark uses the same execution window and
the point-in-time executable universe. Event and benchmark rows therefore share
identical timing.

### 5.3 Backtest engine

Weight output is upgraded from a bare date index to an execution contract:

```text
signal_date
execution_date
execution_price   # next_open | next_close
weights
```

Data-dependent defaults use `next_open`. Equal/fixed allocations may use an
explicit user-selected execution rule. Costs and turnover are charged at the
execution timestamp. Same-close signal/fill is rejected by validation.

No corrected performance number is published until the causal/execution guard
tests pass and the affected artifacts are rebuilt from the corrected code.

## 6. Valuation contract

### 6.1 KR stock detail

The API returns a nested object instead of three unqualified numbers:

```text
valuation
  source: "KRX"
  as_of
  price_as_of
  per, pbr, dividend_yield
  eps, bps, dps
  status              # ok | stale | not_meaningful | unavailable | not_applicable
  missing_reason      # loss_or_zero_eps | nonpositive_bps | source_missing | ...
```

Price and fundamentals are joined on `(date, ticker)` with one-to-one
validation. The page may show a newer tradable price separately, but it never
implies that an older official PER used that newer price.

PER/PBR zero markers are classified using EPS/BPS:

- `EPS <= 0`: PER is `not_meaningful`, not “cheap” and not generic missing;
- `BPS <= 0`: PBR is `not_meaningful`;
- positive denominator with zero ratio: `source_missing` and a quality alert;
- ETF: `not_applicable`.

### 6.2 Market Valuation

The daily artifact adds:

```text
total_names
per_names
per_name_coverage_pct
per_mktcap_coverage_pct
pbr_names
pbr_name_coverage_pct
pbr_mktcap_coverage_pct
loss_or_zero_eps_names
aggregate_earnings_yield
```

The existing positive-earner harmonic PER remains, but the UI labels it and
shows coverage beside it. Aggregate earnings yield uses all usable EPS and
shares, including negative earnings, and is shown as a companion rather than
blindly inverted when nonpositive.

Current percentile is computed against history available through the current
as-of date. Historical decision features use expanding percentiles only. A
full-sample percentile must not be reused as a historical signal.

### 6.3 US valuation

US PER/PBR is a separate later phase:

- price: Massive close with explicit as-of;
- financials: SEC facts with `filed <= as_of`;
- P/E: TTM diluted EPS when a valid four-quarter chain exists;
- P/B: latest filed equity with a point-in-time share/market-cap basis;
- negative EPS and taxonomy gaps remain non-meaningful/unavailable;
- the API exposes financial period and filing date.

The existing annual SEC facts card remains available and is not relabelled as a
valuation multiple.

## 7. API and UI changes

### 7.1 Price endpoints

`/price/{meta_id}` and `/price/{meta_id}/summary` add:

```text
series_meta
close
price_adj_close
total_return_index
metrics.return_basis
valuation
```

The compatibility fields stay for one release. Client types are migrated before
the compatibility fields are removed.

### 7.2 Stock page

- Header: actual close and `Price as of`.
- Chart toggle: `Price | Total Return`.
- Return cards: badge such as `Total Return · Gross` or
  `Price Return · Distributions excluded`.
- `Valuation`: `PER`, `PBR`, `Dividend Yield` with `as of` and Korean tooltip.
- Meaningful empty states: `Loss-making`, `Not applicable`, `Source unavailable`.

### 7.3 Insight page

`Market Valuation` adds name and market-cap coverage beneath PER/PBR. The help
text explains that positive-earner PER excludes loss-making companies.

`Factor Lens` and `Signal Study` show:

```text
Signal: D close · Execution: D+1 open · Return: Gross Total Return
```

### 7.4 Data Trust

Add `Calculation Basis` cards for:

- KR Stock Prices
- KR ETF Prices
- KR Cash Distributions
- US Total Return
- KR Valuation
- Factor/Signal Calculation Version

Each card shows price/event as-of dates, return basis, coverage start/state,
schema/calculation version, row/event counts, unmatched events, and the latest
validation result.

## 8. Pipeline and atomic cutover

The EC2 full pipeline order becomes:

```text
KR/ETF price + master collection
          |
official cash-distribution collection
          |
raw sync -> clean build -> validation
          |
qdata clean publish
          |
Insight artifacts v2
          |
calculation manifest publish
```

`calculation_manifest.json` binds all dependent outputs to one `build_id`:

```text
build_id
qdata_schema_version
price_as_of
event_as_of
asset_master_as_of
return_calculation_version
valuation_calculation_version
coverage_state
built_at
```

The API uses a new build only when the manifest and all required files share the
same build ID. A partial publish leaves the prior complete build active.

Cutover flags mirror the existing US pattern:

```text
KR_RETURN_SCHEMA_V2=1
KR_TOTAL_RETURN_CUTOVER=1
RESEARCH_EXECUTION_V2=1
```

The flags are enabled in that order only after their gates pass. They are not a
permanent branch; after one stable release the old paths and flags are removed.

## 9. Tests and acceptance gates

### 9.1 Unit and contract tests

- no-event total return equals price return;
- split before/after dividend converts cash to the correct current-share basis;
- multiple same-day cash events sum exactly once;
- reverse split, special distribution, ticker rename, delisting fixtures;
- requested-range load includes the prior anchor session but does not leak it
  into the response;
- `latest_price == close`, never wealth-index value;
- mixed total-return coverage fails closed;
- all joins declare cardinality and assert pre/post row counts;
- PER/PBR/DIV formula tolerances and zero classifications;
- market coverage reconciles to the valuation input universe.

### 9.2 Causality and execution guards

- truncating data after `D` cannot change the score or target for `D`;
- perturbing `D+1` or later cannot change a `D` signal/rank;
- every data-dependent `execution_date` is later than `signal_date`;
- no event return includes the entry-date ex-distribution for a buyer entering
  at that open;
- rank operations are within date only;
- no backfill or current master is used to reconstruct a historical universe.

### 9.3 Production gates

- price/fundamental latest settled session is within policy;
- KRX official return reconciliation stays within the declared tolerance;
- canonical distribution events have zero unmatched identities for a complete
  claim;
- major ETF issuer fixtures and known monthly/quarterly events reconcile;
- active and delisted event coverage is published separately;
- app artifact and qdata manifest versions agree;
- an API smoke test confirms labels, dates, basis, and a known distribution day;
- Data Trust shows no unknown basis for a decision-facing component.

## 10. Rollout order

### Phase 0 — Contract and source proof

1. Accept quant-data ADR-0008 and this design.
2. Probe KSD/SEIBro and KRX KIND contracts, automation terms, identifiers,
   revisions, and historical/delisted coverage.
3. Freeze fixtures before writing the builder.

### Phase 1 — Immediate correctness without synthetic dividends

1. Add explicit basis metadata and honest UI labels.
2. Stop aliasing KR ETF raw close as adjusted close. Implemented with a KRX
   reference-price-adjusted basis plus explicit raw fallback for legacy rows.
3. Add valuation dates, inputs, missing reasons, and market coverage.
4. Replace Factor Lens and Signal Study same-close calculations with v2
   next-open timing using price return.
5. Publish calculation versions in Data Trust.

### Phase 2 — KR distribution and total-return support

1. Add stable identity/ISIN enrichment.
2. Collect, build, validate, and publish official cash events.
3. Add ETF capital-action adjustment. Implemented from KRX `FLUC_RT`; exact
   cash-event total return remains gated.
4. Introduce the common return composer and migrate stock metrics, comparison,
   simulation, optimization, and research artifacts.
5. Enable total return only over complete common coverage.

### Phase 3 — Unified execution and US valuation

1. Expose the current general engine's signal/execution dates and reject mixed
   return bases. Implemented for the close-execution engine; next-open remains a
   separately gated migration.
2. Add SEC filing-date-safe US TTM valuation.
3. Remove legacy ambiguous fields after one stable release.

## 11. Definition of done

The work is complete only when:

1. no decision-facing code reads an unqualified `adj_close`;
2. every return display declares price or total return;
3. KR ETF is never described as adjusted while it is raw;
4. cash distributions are exact official events or explicitly unavailable;
5. all data-dependent studies execute after their signal timestamp;
6. PER/PBR show source date and meaningful missing status;
7. market valuation exposes coverage;
8. mixed-basis portfolios fail rather than silently continue;
9. Data Trust exposes calculation and coverage versions;
10. the old RDS source remains absent from every price, master, valuation, and
    corporate-action path.
