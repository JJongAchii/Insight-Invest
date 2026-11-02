"""Institution-aware primary selection plus the pass-only fill-state supplement.

The primary is the approved `InstitutionalSelector` (temporal OOF q). The
supplement is the approved `Complement`: its value model, q and threshold are
learned only on historically predicted original-t01 passes, and it can add only
events that the original t01 rule passes today. Both parts fit on the same
mature training rows; the union adds no input, grid or threshold of its own.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ipo_open_entry.recall import data as D
from ipo_open_entry.recall.complement import STATES, Complement
from ipo_open_entry.recall.institution import InstitutionalSelector


class Union:
    def __init__(self, institution=None, complement=None):
        complement = dict(complement or {"mode": "states"})
        if complement.get("mode", "direct") == "admission":
            raise ValueError("the union supplements with a value model, not legacy admission")
        self.primary = InstitutionalSelector(**(institution or {}))
        self.supplement = Complement(**complement)
        self.cfg = D.spec()

    def fit(self, train, cutoff):
        self.primary.fit(train, cutoff)
        self.supplement.fit(train, cutoff)
        self.active = bool(self.supplement.active)
        self.threshold = self.primary.threshold
        self.meta = {
            "q": self.primary.q,
            "threshold": self.primary.threshold,
            "train_events": self.primary.meta["train_events"],
            "oof_events": self.primary.meta["oof_events"],
            "fallback": self.primary.meta["fallback"],
            "supplement_active": self.active,
            "supplement_q": self.supplement.q,
            "primary": self.primary.meta,
            "supplement": self.supplement.meta,
        }
        return self

    def decide(self, frame):
        frame = D.predictors(frame)
        primary = self.primary.decide(frame).set_index("event_id")
        supplement = self.supplement.decide(frame).set_index("event_id")
        supplement = supplement.loc[primary.index]
        primary_buy = primary.buy.to_numpy(dtype=bool)
        supplement_buy = supplement.additional_buy.to_numpy(dtype=bool)
        added = supplement_buy & ~primary_buy
        buy = primary_buy | supplement_buy
        out = pd.DataFrame(
            {
                "event_id": primary.index.to_numpy(),
                "score": primary.score.to_numpy(),
                "buy": buy,
                "limit_mult": np.where(buy, self.cfg["entry_cap"], np.nan),
                "threshold": self.primary.threshold,
                "primary_buy": primary_buy,
                "baseline_buy": supplement.baseline_buy.to_numpy(dtype=bool),
                "supplement_score": supplement.score.to_numpy(),
                "supplement_threshold": self.supplement.threshold,
                "additional_buy": added,
                "institution_component": primary.institution_component.to_numpy(),
                "interaction_component": primary.interaction_component.to_numpy(),
                "decision_reason": np.where(
                    primary_buy,
                    "institution-aware prelisting score >= temporal OOF threshold",
                    np.where(
                        added,
                        "original-t01 pass with fill-state supplement >= pass-population threshold",
                        "institution-aware score below threshold; no supplement",
                    ),
                ),
            }
        )
        for state in STATES:
            column = f"predicted_{state}_probability"
            if column in supplement:
                out[column] = supplement[column].to_numpy()
        return out
