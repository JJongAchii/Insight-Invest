"""A: execution target, B: temporal OOF selection, C: small monotone hinges."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ipo_open_entry.config import load_config
from ipo_open_entry.models import blocks as B
from ipo_open_entry.models import linear as L
from ipo_open_entry.models.common import TrainPercentile
from ipo_open_entry.models.regression import SignedRegression
from ipo_open_entry.signal.data import mature_before, predictors, spec


def incumbent() -> SignedRegression:
    cfg = spec()
    return SignedRegression(
        "top",
        cfg["blocks"],
        "train",
        cfg["shrinkage"],
        True,
        "rank",
        top_grid=cfg["q_grid"],
        entry_cap=cfg["entry_cap"],
    )


class HingeDesign(L.Design):
    """Training-only block knots. Each hinge shares the block's prescribed sign."""

    def __init__(self, blocks, horizon, pct, quantiles):
        super().__init__(blocks, B.UNCONDITIONAL, horizon, True, True)
        vals = B.block_values(pct, self.blocks, horizon)
        self.knots = {}
        for block in self.blocks:
            known = vals[block].dropna().to_numpy()
            self.knots[block] = np.quantile(known, quantiles) if len(known) else np.array([])
        for block, knots in self.knots.items():
            self.names.extend(f"hinge:{block}:{j}" for j in range(len(knots)))
        extra = sum(len(k) for k in self.knots.values())
        self.lower = np.r_[self.lower, np.zeros(extra)]
        self.upper = np.r_[self.upper, np.full(extra, np.inf)]

    def matrix(self, pct, regimes):
        base = super().matrix(pct, regimes)
        vals = B.block_values(pct, self.blocks, self.horizon)
        cols = [base]
        for block, knots in self.knots.items():
            v = vals[block].to_numpy(dtype=float)
            signs = np.array(
                [L._numeric(B.sign(B.UNCONDITIONAL, block, r, self.horizon)) for r in regimes]
            )
            for knot in knots:
                cols.append(
                    (signs * np.where(np.isfinite(v), np.maximum(v - knot, 0.0), 0.0))[:, None]
                )
        return np.column_stack(cols)


class Core:
    """Fit scores without selecting q; the legacy path delegates to frozen t01."""

    def __init__(self, target="legacy", label="rank", knots="none", shrinkage=300):
        cfg = spec()
        if target not in ("legacy", "exact") or label not in ("rank", "growth"):
            raise ValueError("unapproved target/label")
        if knots not in ("none", *cfg["hinge_knots"]):
            raise ValueError("unapproved hinge knots")
        if target == "legacy" and label != "rank":
            raise ValueError("legacy per-horizon rank targets are frozen")
        if knots == "none" and shrinkage != cfg["shrinkage"]:
            raise ValueError("linear shrinkage is frozen")
        if knots != "none" and shrinkage not in cfg["hinge_shrinkage_menu"]:
            raise ValueError("unapproved hinge shrinkage")
        self.target, self.label, self.knots, self.shrinkage = target, label, knots, shrinkage
        self.cfg = cfg

    def growth(self, table):
        if self.target == "legacy":
            return B.growth_cap_by_h(table, load_config()).mean(axis=1).to_numpy()
        return table["sig_growth"].to_numpy(dtype=float)

    def fit(self, train):
        if self.target == "legacy":
            self.model = incumbent()
            if self.knots == "none":
                self.model.fit(train)
            else:
                # Preserve t01's separate H1/H2/H3 rank fits and prediction average.
                # C changes only each horizon's additive basis and allowed pooling k.
                self.model.shrinkage = self.shrinkage
                self.model.ref_ = TrainPercentile(self.model.columns).fit(train)
                pct = self.model.ref_.transform(train)
                regimes = train.regime.to_numpy()
                growth = B.growth_cap_by_h(train, self.model.config)
                self.model.coefs_ = {}
                for h in B.HORIZONS:
                    y = growth[f"g{h}"].to_numpy()
                    ok = np.isfinite(y)
                    y = pd.Series(np.where(ok, y, np.nan)).rank(pct=True).to_numpy() - 0.5
                    design = HingeDesign(
                        self.model.blocks, h, pct, self.cfg["hinge_knots"][self.knots]
                    )
                    self.model.designs[h] = design
                    z = design.matrix(pct, regimes)
                    self.model.coefs_[h] = L.partial_pool(
                        z[ok], y[ok], regimes[ok], design, self.shrinkage
                    )
            return self
        blocks = tuple(self.cfg["blocks"])
        cols = [*B.feature_columns(blocks), L.CONTROL]
        self.ref = TrainPercentile(cols).fit(train)
        pct = self.ref.transform(train)
        h = self.cfg["horizon"]
        self.design = (
            L.Design(blocks, B.UNCONDITIONAL, h, True, True)
            if self.knots == "none"
            else HingeDesign(blocks, h, pct, self.cfg["hinge_knots"][self.knots])
        )
        y = self.growth(train)
        if self.label == "rank":
            y = pd.Series(y).rank(pct=True).to_numpy() - 0.5
        z = self.design.matrix(pct, train.regime.to_numpy())
        self.coefs = L.partial_pool(z, y, train.regime.to_numpy(), self.design, self.shrinkage)
        return self

    def predict(self, frame):
        if self.target == "legacy":
            return self.model._predict(frame)
        z = self.design.matrix(self.ref.transform(frame), frame.regime.to_numpy())
        return L.predict(z, frame.regime.to_numpy(), self.coefs)


def inner_folds(train: pd.DataFrame, cutoff: pd.Timestamp, cfg: dict):
    starts = pd.date_range(end=cutoff, periods=cfg["inner_quarters"] + 1, freq="QS")[:-1]
    for qs in starts:
        qe = qs + pd.offsets.QuarterBegin(startingMonth=1)
        fitting = mature_before(train, qs)
        valid = train[
            (train.listing_date >= qs)
            & (train.listing_date < qe)
            & (train.label_available < cutoff)
        ].copy()
        if len(fitting) >= cfg["inner_min_train"] and len(valid):
            yield qs, fitting, valid


class Signal:
    def __init__(
        self, target="legacy", selection="train", label="rank", knots="none", shrinkage=300
    ):
        if selection not in ("train", "oof"):
            raise ValueError("unapproved selection")
        self.args = dict(target=target, label=label, knots=knots, shrinkage=shrinkage)
        self.selection = selection
        self.cfg = spec()

    def fit(self, train: pd.DataFrame, cutoff: pd.Timestamp):
        # Sorting is explicit because rank ties and temporal fold order must be repeatable.
        train = train.sort_values(["listing_date", "event_id"]).reset_index(drop=True)
        if not (train.label_available < cutoff).all():
            raise ValueError("training includes immature labels")
        self.core = Core(**self.args).fit(train)
        scores = self.core.predict(predictors(train))
        self.fold_meta = []
        totals = np.zeros(len(self.cfg["q_grid"]))
        self.oof_events = 0
        if self.selection == "train":
            realized = self.core.growth(train)
            for j, q in enumerate(self.cfg["q_grid"]):
                totals[j] = realized[scores >= np.quantile(scores, 1 - q)].sum()
        else:
            for qs, fitting, valid in inner_folds(train, cutoff, self.cfg):
                core = Core(**self.args).fit(fitting)
                fit_scores = core.predict(predictors(fitting))
                valid_scores = core.predict(predictors(valid))
                realized = core.growth(valid)
                for j, q in enumerate(self.cfg["q_grid"]):
                    tau = np.quantile(fit_scores, 1 - q)
                    totals[j] += realized[valid_scores >= tau].sum()
                self.oof_events += len(valid)
                self.fold_meta.append(
                    {
                        "quarter": str(qs.date()),
                        "train_events": len(fitting),
                        "valid_events": len(valid),
                        "max_train_label_date": str(fitting.label_available.max().date()),
                    }
                )
        self.fallback = self.selection == "oof" and self.oof_events < self.cfg["inner_min_oof"]
        self.q = (
            self.cfg["fallback_q"] if self.fallback else self.cfg["q_grid"][int(np.argmax(totals))]
        )
        self.threshold = float(np.quantile(scores, 1 - self.q))
        self.train_events = len(train)
        return self

    def decide(self, frame: pd.DataFrame):
        score = self.core.predict(predictors(frame))
        buy = score >= self.threshold
        return pd.DataFrame(
            {
                "event_id": frame.event_id.to_numpy(),
                "score": score,
                "buy": buy,
                "limit_mult": np.where(buy, self.cfg["entry_cap"], np.nan),
            }
        )


def walk_forward(table: pd.DataFrame, variant: dict):
    cfg = spec()
    out, diagnostics = [], []
    for qs in pd.date_range(cfg["evaluation_start"], table.listing_date.max(), freq="QS"):
        qe = qs + pd.offsets.QuarterBegin(startingMonth=1)
        test = table[(table.listing_date >= qs) & (table.listing_date < qe)]
        if test.empty:
            continue
        train = mature_before(table, qs)
        model = Signal(**variant).fit(train, qs)
        for _, day in test.groupby("listing_date"):
            out.append(model.decide(predictors(day)).assign(quarter=qs))
        diagnostics.append(
            {
                "quarter": str(qs.date()),
                "q": model.q,
                "threshold": model.threshold,
                "train_events": model.train_events,
                "oof_events": model.oof_events,
                "fallback": model.fallback,
                "inner_folds": model.fold_meta,
            }
        )
    if not out:
        raise ValueError("no evaluation events")
    return pd.concat(out, ignore_index=True), diagnostics
