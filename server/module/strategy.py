from datetime import timedelta

import numpy as np
import pandas as pd

from .util import resample_data


def cal_monthly_momentum(price: pd.DataFrame):

    price_tail = resample_data(price=price, freq="M", type="tail")[-13:]

    if len(price_tail) < 13:
        return

    monthly_momentum = price_tail.iloc[-1].div(price_tail) - 1

    return monthly_momentum


def binary_from_momentum(momentum: pd.DataFrame):

    return momentum.apply(lambda x: np.where(x > 0, 1, 0))


def absolute_momentum(price: pd.DataFrame):
    monthly_mmt = cal_monthly_momentum(price=price)

    if monthly_mmt is None:
        return
    abs_mmt = binary_from_momentum(momentum=monthly_mmt)[:-1]
    abs_mmt_score = abs_mmt.mean()

    return abs_mmt_score


class EqualWeight:
    def simulate(self, price: pd.DataFrame):
        weights = resample_data(price=price).copy()
        weights[:] = 1 / len(price.columns)
        return weights


class DualMomentum:
    def simulate(self, price: pd.DataFrame):

        weights_df = pd.DataFrame()

        rebal_date = resample_data(price=price, freq="M", type="head").index

        # simulate historical date
        for rebal_date in rebal_date:
            yesterday = rebal_date - timedelta(days=1)

            price_slice = price[:yesterday]

            if not price_slice.empty:

                abs_mmt_score = absolute_momentum(price=price_slice)

                if abs_mmt_score is None:
                    continue

                dual_mmt_score = abs_mmt_score.nlargest(4)

                weights = dual_mmt_score.div(dual_mmt_score.sum()).reset_index()

                weights.columns = ["ticker", "weights"]
                weights["rebal_date"] = rebal_date
                weights_df = pd.concat([weights_df, weights], axis=0)

        return weights_df.pivot(index="rebal_date", columns="ticker", values="weights")
