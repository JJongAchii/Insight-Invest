"""Recall models share the original decision boundary and fixed trading rule."""

from __future__ import annotations

import pandas as pd

from ipo_open_entry.recall import data as D
from ipo_open_entry.recall.complement import Complement
from ipo_open_entry.recall.institution import InstitutionalSelector
from ipo_open_entry.recall.union import Union
from ipo_open_entry.signal.models import Signal


class Model:
    def __init__(self, family="baseline", selection="train", **kwargs):
        self.family = family
        if family == "baseline":
            if kwargs:
                raise ValueError("baseline is frozen")
            self.model = Signal(target="legacy", selection=selection)
        elif family == "institution":
            if selection != "oof":
                raise ValueError("institutional selection must use OOF")
            self.model = InstitutionalSelector(**kwargs)
        elif family == "complement":
            if selection != "oof":
                raise ValueError("complement selection must use OOF")
            self.model = Complement(**kwargs)
        elif family == "union":
            if selection != "oof":
                raise ValueError("union selection must use OOF")
            self.model = Union(**kwargs)
        else:
            raise ValueError("unimplemented or unapproved family")

    def fit(self, train, cutoff):
        self.model.fit(train, cutoff)
        if self.family != "baseline":
            self.meta = self.model.meta
            return self
        self.meta = {
            "q": self.model.q,
            "threshold": self.model.threshold,
            "train_events": self.model.train_events,
            "oof_events": self.model.oof_events,
            "fallback": self.model.fallback,
            "inner_folds": self.model.fold_meta,
        }
        return self

    def decide(self, frame):
        out = self.model.decide(D.predictors(frame))
        if self.family != "baseline":
            return out
        out["threshold"] = self.model.threshold
        out["decision_reason"] = out.buy.map(
            {
                True: "legacy score >= train-derived threshold",
                False: "legacy score < train-derived threshold",
            }
        )
        return out


def walk_forward(table, variant):
    cfg = D.spec()
    out, diagnostics = [], []
    for qs in pd.date_range(cfg["evaluation_start"], table.listing_date.max(), freq="QS"):
        qe = qs + pd.offsets.QuarterBegin(startingMonth=1)
        test = table[(table.listing_date >= qs) & (table.listing_date < qe)]
        if test.empty:
            continue
        model = Model(**variant).fit(D.mature_before(table, qs), qs)
        for _, day in test.groupby("listing_date"):
            out.append(model.decide(D.predictors(day)).assign(quarter=qs))
        diagnostics.append({"quarter": str(qs.date()), **model.meta})
    if not out:
        raise ValueError("no evaluation events")
    return pd.concat(out, ignore_index=True), diagnostics
