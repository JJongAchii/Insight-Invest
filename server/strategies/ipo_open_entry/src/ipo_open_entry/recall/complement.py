"""Supplement original passes using only historical out-of-fit pass membership."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ipo_open_entry.models import blocks as B
from ipo_open_entry.models import linear as L
from ipo_open_entry.models.common import TrainPercentile
from ipo_open_entry.recall import data as D
from ipo_open_entry.recall.institution import InstitutionalDesign
from ipo_open_entry.signal.models import Signal, inner_folds

STATES = ("open", "intraday", "unfilled")


def historical_passes(table):
    """Membership and scores from each listing quarter's prior mature history.

    This intentionally does not classify the training set using the final fitted
    baseline. Earlier rows without 80 mature training events remain unknown.
    """
    cfg = D.spec()
    rows = []
    starts = sorted(table.listing_date.dt.to_period("Q").dt.start_time.unique())
    for start in starts:
        qs = pd.Timestamp(start)
        qe = qs + pd.offsets.QuarterBegin(startingMonth=1)
        fitting = D.mature_before(table, qs)
        valid = table[(table.listing_date >= qs) & (table.listing_date < qe)]
        if len(fitting) < cfg["inner_min_train"]:
            continue
        baseline = Signal(target="legacy", selection="train").fit(fitting, qs)
        decision = baseline.decide(D.predictors(valid))
        rows.append(
            decision[["event_id", "buy", "score"]]
            .rename(columns={"buy": "history_base_buy", "score": "history_base_score"})
            .assign(
                history_fit_cutoff=qs,
                history_max_label=fitting.label_available.max(),
            )
        )
    columns = [
        "event_id",
        "history_base_buy",
        "history_base_score",
        "history_fit_cutoff",
        "history_max_label",
    ]
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=columns)


def annotate_history(train):
    return train.merge(historical_passes(train), on="event_id", how="left", validate="one_to_one")


def known_passes(table):
    return table[table.history_base_buy.notna() & table.history_base_buy.eq(False)].copy()


class ValueCore:
    """Small shared linear value or prelisting fill-state mixture.

    State indicators are targets only. Each state-specific conditional fit needs
    30 mature events; otherwise its probability/value falls back to a pooled mean.
    Clipped probability estimates are normalized to one before forming value.
    """

    def __init__(self, mode="direct", interactions=False, shrinkage=300):
        if mode not in ("direct", "states") or shrinkage not in D.spec()["shrinkage_menu"]:
            raise ValueError("unapproved complement value model")
        self.mode, self.interactions, self.shrinkage = mode, interactions, shrinkage

    def fit(self, train):
        columns = [*B.feature_columns(B.ALL_BLOCKS), L.CONTROL]
        self.ref = TrainPercentile(columns).fit(train)
        self.design = InstitutionalDesign(2, self.interactions)
        # Fill probability and conditional value have no registered monotone signs.
        self.design.lower = np.full(len(self.design.names), -np.inf)
        z = self.design.matrix(self.ref.transform(train), train.regime)
        y, regimes = train.sig_growth.to_numpy(), train.regime.to_numpy()
        self.pooled = float(np.mean(y)) if len(y) else 0.0
        self.support = {
            "events": len(train),
            "fillable": int(train.sig_filled.sum()),
            "positive": int((train.sig_net > 0).sum()),
            "negative": int((train.sig_net < 0).sum()),
            "states": {s: int(train.sig_fill_type.eq(s).sum()) for s in STATES},
        }
        if self.mode == "direct":
            self.coef = L.partial_pool(z, y, regimes, self.design, self.shrinkage)
        else:
            self.state_models = {}
            filled = train.sig_filled.to_numpy(dtype=bool)
            self.pooled_filled = float(y[filled].mean()) if filled.any() else 0.0
            for state in STATES:
                mask = train.sig_fill_type.eq(state).to_numpy()
                supported = int(mask.sum()) >= D.spec()["min_state"]
                prob = (
                    L.partial_pool(z, mask.astype(float), regimes, self.design, self.shrinkage)
                    if supported
                    else None
                )
                value = None
                if supported and state != "unfilled":
                    value = L.partial_pool(
                        z[mask], y[mask], regimes[mask], self.design, self.shrinkage
                    )
                self.state_models[state] = {
                    "prior": float(mask.mean()),
                    "prob": prob,
                    "value": value,
                    "supported": supported,
                }
        return self

    def predict_details(self, frame):
        frame = D.predictors(frame)
        z = self.design.matrix(self.ref.transform(frame), frame.regime)
        regimes = frame.regime.to_numpy()
        if self.mode == "direct":
            return L.predict(z, regimes, self.coef), None
        probability, values = [], []
        for state in STATES:
            m = self.state_models[state]
            p = (
                np.full(len(frame), m["prior"])
                if m["prob"] is None
                else L.predict(z, regimes, m["prob"])
            )
            probability.append(np.clip(p, 0.0, 1.0))
            v = np.zeros(len(frame))
            if state != "unfilled":
                v = (
                    np.full(len(frame), self.pooled_filled)
                    if m["value"] is None
                    else L.predict(z, regimes, m["value"])
                )
            values.append(v)
        p = np.column_stack(probability)
        zero = p.sum(axis=1) <= 0
        if zero.any():
            p[zero] = [self.state_models[s]["prior"] for s in STATES]
        p /= p.sum(axis=1, keepdims=True)
        return (p * np.column_stack(values)).sum(axis=1), p

    def predict(self, frame):
        return self.predict_details(frame)[0]


class Complement:
    def __init__(self, mode="direct", interactions=False, shrinkage=300):
        if mode not in ("direct", "states", "admission"):
            raise ValueError("unapproved supplement")
        self.mode, self.interactions, self.shrinkage = mode, interactions, shrinkage
        self.cfg = D.spec()

    def _core(self, train):
        return ValueCore(self.mode, self.interactions, self.shrinkage).fit(train)

    def fit(self, train, cutoff):
        train = train.sort_values(["listing_date", "event_id"]).reset_index(drop=True)
        if not (train.label_available < cutoff).all():
            raise ValueError("training includes immature labels")
        self.baseline = Signal(target="legacy", selection="train").fit(train, cutoff)
        annotated = annotate_history(train)
        passes = known_passes(annotated)
        self.core = None
        enough = int(passes.sig_filled.sum()) >= self.cfg["min_leaf_fillable"]
        if enough and self.mode != "admission":
            self.core = self._core(passes)
        totals = np.zeros(len(self.cfg["q_grid"]) + 1)
        n_oof, folds = 0, []
        for qs, fitting, valid in inner_folds(annotated, cutoff, self.cfg):
            fit_pass, valid_pass = known_passes(fitting), known_passes(valid)
            supported = int(fit_pass.sig_filled.sum()) >= self.cfg["min_leaf_fillable"]
            fold = {
                "quarter": str(qs.date()),
                "train_events": len(fitting),
                "train_pass_events": len(fit_pass),
                "train_pass_fillable": int(fit_pass.sig_filled.sum()),
                "train_pass_positive": int((fit_pass.sig_net > 0).sum()),
                "train_pass_negative": int((fit_pass.sig_net < 0).sum()),
                "valid_pass_events": len(valid_pass),
                "supported": supported,
                "max_train_label_date": str(fitting.label_available.max().date()),
            }
            folds.append(fold)
            if not supported or valid_pass.empty:
                continue
            if self.mode == "admission":
                baseline = Signal(target="legacy", selection="train").fit(fitting, qs)
                fit_scores = baseline.core.predict(D.predictors(fit_pass))
                valid_scores = baseline.core.predict(D.predictors(valid_pass))
            else:
                core = self._core(fit_pass)
                fit_scores, valid_scores = core.predict(fit_pass), core.predict(valid_pass)
                fold["state_support"] = core.support
            realized = valid_pass.sig_growth.to_numpy()
            for j, q in enumerate(self.cfg["q_grid"], 1):
                totals[j] += realized[valid_scores >= np.quantile(fit_scores, 1 - q)].sum()
            n_oof += len(valid_pass)
        selected = int(np.argmax(totals))
        self.active = bool(enough and n_oof >= self.cfg["inner_min_oof"] and selected > 0)
        self.q = self.cfg["q_grid"][selected - 1] if self.active else 0.0
        self.threshold = np.inf
        if self.active:
            score = (
                self.baseline.core.predict(D.predictors(passes))
                if self.mode == "admission"
                else self.core.predict(passes)
            )
            self.threshold = float(np.quantile(score, 1 - self.q))
        self.meta = {
            "q": self.q,
            "threshold": self.threshold,
            "train_events": len(train),
            "train_pass_events": len(passes),
            "train_pass_fillable": int(passes.sig_filled.sum()),
            "train_pass_positive": int((passes.sig_net > 0).sum()),
            "train_pass_negative": int((passes.sig_net < 0).sum()),
            "oof_events": n_oof,
            "oof_population": "historically predicted passes only",
            "fallback": not self.active,
            "inner_folds": folds,
            "q_candidates": len(totals),
            "q_grid_totals": totals.tolist(),
            "baseline_q": self.baseline.q,
            "state_support": self.core.support if self.core is not None else None,
            "history_known_events": int(annotated.history_base_buy.notna().sum()),
            "history_membership": annotated.loc[
                annotated.history_base_buy.notna(),
                ["event_id", "history_base_buy", "history_fit_cutoff", "history_max_label"],
            ].to_dict("records"),
        }
        return self

    def decide(self, frame):
        frame = D.predictors(frame)
        base = self.baseline.decide(frame)
        p = None
        if self.mode == "admission":
            score = base.score.to_numpy()
        elif self.core is not None:
            score, p = self.core.predict_details(frame)
        else:
            score = np.zeros(len(frame))
        additional = (~base.buy.to_numpy()) & self.active & (score >= self.threshold)
        buy = base.buy.to_numpy() | additional
        out = pd.DataFrame(
            {
                "event_id": frame.event_id.to_numpy(),
                "score": score,
                "buy": buy,
                "limit_mult": np.where(buy, self.cfg["entry_cap"], np.nan),
                "threshold": self.threshold,
                "baseline_buy": base.buy.to_numpy(),
                "baseline_score": base.score.to_numpy(),
                "baseline_threshold": self.baseline.threshold,
                "additional_buy": additional,
                "decision_reason": np.where(
                    base.buy,
                    "original t01 buy retained",
                    np.where(
                        additional,
                        "historical-pass supplement >= temporal pass-population threshold",
                        "no supplement: support/fold value/threshold rule",
                    ),
                ),
            }
        )
        if p is not None:
            for j, state in enumerate(STATES):
                out[f"predicted_{state}_probability"] = p[:, j]
        return out
