"""Small train-only institutional response models; no postlisting predictors."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ipo_open_entry.config import load_config
from ipo_open_entry.models import blocks as B
from ipo_open_entry.models import linear as L
from ipo_open_entry.models.common import TrainPercentile
from ipo_open_entry.recall import data as D
from ipo_open_entry.signal.models import inner_folds


class InstitutionalDesign(L.Design):
    """Original signed blocks plus separate H2/H3 values in both regimes.

    Only three registered centered products are available. Their scaling comes
    from the same training-only percentile reference as the primitive terms.
    """

    def __init__(self, horizon, interactions=False, institutional_sign="free"):
        cfg = D.spec()
        super().__init__(tuple(cfg["blocks"]), B.UNCONDITIONAL, horizon, True, True)
        self.base_width = len(self.names)
        self.raw = cfg["raw_institution_columns"]
        self.products = cfg["interaction_columns"] if interactions else []
        if institutional_sign not in ("free", "positive"):
            raise ValueError("unapproved institutional sign")
        self.names += [f"raw:{c}" for c in self.raw]
        self.names += [f"miss_raw:{c}" for c in self.raw]
        self.names += [f"interaction:institution_x_{c}" for c in self.products]
        raw_lower = -np.inf if institutional_sign == "free" else 0.0
        self.lower = np.r_[
            self.lower,
            np.full(len(self.raw), raw_lower),
            np.full(len(self.raw) + len(self.products), -np.inf),
        ]
        self.upper = np.full(len(self.names), np.inf)

    def matrix(self, pct, regimes):
        base = super().matrix(pct, regimes)

        def centered(c):
            return np.nan_to_num(pct[c].to_numpy(dtype=float) - 0.5, nan=0.0)

        columns = [base, *[centered(c)[:, None] for c in self.raw]]
        columns += [pct[c].isna().to_numpy(dtype=float)[:, None] for c in self.raw]
        demand = centered("h3_bookbuild_ratio")
        columns += [(demand * centered(c))[:, None] for c in self.products]
        return np.column_stack(columns)


class InstitutionalCore:
    def __init__(self, interactions=False, shrinkage=300, institutional_sign="free"):
        cfg = D.spec()
        if shrinkage not in cfg["shrinkage_menu"]:
            raise ValueError("unapproved shrinkage")
        self.interactions = bool(interactions)
        self.shrinkage = shrinkage
        self.institutional_sign = institutional_sign
        self.columns = [*B.feature_columns(B.ALL_BLOCKS), L.CONTROL]

    def fit(self, train):
        self.ref = TrainPercentile(self.columns).fit(train)
        pct, regimes = self.ref.transform(train), train.regime.to_numpy()
        self.designs, self.coefs = {}, {}
        growth = B.growth_cap_by_h(train, load_config())
        for h in B.HORIZONS:
            design = InstitutionalDesign(h, self.interactions, self.institutional_sign)
            y = growth[f"g{h}"].rank(pct=True).to_numpy() - 0.5
            self.coefs[h] = L.partial_pool(
                design.matrix(pct, regimes), y, regimes, design, self.shrinkage
            )
            self.designs[h] = design
        return self

    def predict(self, frame):
        return self.components(frame)["score"]

    def components(self, frame):
        frame = D.predictors(frame)
        pct, regimes = self.ref.transform(frame), frame.regime.to_numpy()
        out = {k: np.zeros(len(frame)) for k in ["score", "institution", "interaction"]}
        for h in B.HORIZONS:
            design = self.designs[h]
            z = design.matrix(pct, regimes)
            width = design.base_width
            for regime in L.REGIMES:
                mask = regimes == regime
                coef = self.coefs[h][regime]
                out["score"][mask] += z[mask] @ coef / len(B.HORIZONS)
                end = width + 2 * len(design.raw)
                out["institution"][mask] += z[mask, width:end] @ coef[width:end] / len(B.HORIZONS)
                out["interaction"][mask] += z[mask, end:] @ coef[end:] / len(B.HORIZONS)
        return out


class InstitutionalSelector:
    """Keep legacy targets and temporal q choice; only the feature response changes."""

    def __init__(self, interactions=False, shrinkage=300, institutional_sign="free"):
        self.args = dict(
            interactions=interactions, shrinkage=shrinkage, institutional_sign=institutional_sign
        )
        self.cfg = D.spec()

    def fit(self, train, cutoff):
        train = train.sort_values(["listing_date", "event_id"]).reset_index(drop=True)
        if not (train.label_available < cutoff).all():
            raise ValueError("training includes immature labels")
        self.core = InstitutionalCore(**self.args).fit(train)
        scores = self.core.predict(D.predictors(train))
        totals = np.zeros(len(self.cfg["q_grid"]))
        folds, n_oof = [], 0
        for qs, fitting, valid in inner_folds(train, cutoff, self.cfg):
            core = InstitutionalCore(**self.args).fit(fitting)
            fit_score, valid_score = core.predict(fitting), core.predict(valid)
            realized = B.growth_cap_by_h(valid, load_config()).mean(axis=1).to_numpy()
            for j, q in enumerate(self.cfg["q_grid"]):
                totals[j] += realized[valid_score >= np.quantile(fit_score, 1 - q)].sum()
            n_oof += len(valid)
            folds.append(
                {
                    "quarter": str(qs.date()),
                    "train_events": len(fitting),
                    "valid_events": len(valid),
                    "max_train_label_date": str(fitting.label_available.max().date()),
                }
            )
        fallback = n_oof < self.cfg["inner_min_oof"]
        self.q = self.cfg["fallback_q"] if fallback else self.cfg["q_grid"][int(np.argmax(totals))]
        self.threshold = float(np.quantile(scores, 1 - self.q))
        self.meta = {
            "q": self.q,
            "threshold": self.threshold,
            "train_events": len(train),
            "oof_events": n_oof,
            "fallback": fallback,
            "inner_folds": folds,
            "q_grid_totals": totals.tolist(),
            "q_candidates": len(totals),
            "linear_fits": len(B.HORIZONS) * (len(folds) + 1),
            "coefficient_names": {h: d.names for h, d in self.core.designs.items()},
            "coefficients": self.core.coefs,
        }
        return self

    def decide(self, frame):
        parts = self.core.components(D.predictors(frame))
        buy = parts["score"] >= self.threshold
        return pd.DataFrame(
            {
                "event_id": frame.event_id.to_numpy(),
                "score": parts["score"],
                "buy": buy,
                "limit_mult": np.where(buy, self.cfg["entry_cap"], np.nan),
                "threshold": self.threshold,
                "institution_component": parts["institution"],
                "interaction_component": parts["interaction"],
                "decision_reason": np.where(
                    buy,
                    "institution-aware prelisting score >= temporal OOF threshold",
                    "institution-aware prelisting score < temporal OOF threshold",
                ),
            }
        )
