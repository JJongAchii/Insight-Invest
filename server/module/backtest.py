import os
import sys
import pandas as pd
from typing import Union, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../..")))
import db
from module.strategy import DualMomentum
from module.util import backtest_result

class Backtest:
    
    def __init__(
        self,
        strategy_name: str = None,
    ) -> None:
        
        self.strategy_name = strategy_name
    
    
    def universe(self, tickers: Union[str, List] = None):
        
        return tickers
        

    def data(
        self,
        meta_id: Union[int, List] = None,
        tickers: Union[str, List] = None,
        source: str = "db"
    ) -> pd.DataFrame:
        
        if source == "db":
            with db.session_local() as session:
                query = (
                    session.query(
                        db.TbMeta.ticker,
                        db.TbPrice.trade_date,
                        db.TbPrice.adj_close,
                    )
                    .join(
                        db.TbPrice,
                        db.TbPrice.meta_id == db.TbMeta.meta_id
                    )
                )
                if meta_id:
                    query = query.filter(db.TbMeta.meta_id.in_(meta_id))
                if tickers:
                    query = query.filter(db.TbMeta.ticker.in_(tickers))
                
                data = db.read_sql_query(query=query, parse_dates="trade_date").pivot(index="trade_date", columns="ticker", values="adj_close")
            
        return data
        
    
    def rebalance(
        self,
        price: pd.DataFrame,
        method: str = "eq",
        freq: str = "M",
        custom_weight: dict = None,
        offensive: List = None,
        defensive: List = None,
        start: ... = None,
        end: ... = None
    ) -> pd.DataFrame:
        """_summary_

        Args:
            method (str, optional): _description_. Defaults to "eq".
            freq (str, optional): _description_. Defaults to "M".
            weight (dict, optional): 
                using when method == "custom"
                ex) weight={"SPY": 0.6, "IEF":0.4}. Defaults to None.
            offensive (List, optional): 
                using when method == "VAA_agg"
                ex) offensive=["SPY", "EFA", "EEM", "AGG"]. Defaults to None.
            defensive (List, optional): 
                using when method == "VAA_agg"
                ex) defensive=["LQD", "IEF", "SHY"]. Defaults to None.

        Returns:
            pd.DataFrame: _description_
        """
        
        price = price.loc[start:end].dropna()
        
        if method == "dual_mmt":
            weights = DualMomentum().simulate(price=price)
        
        # if method == "eq":
        #     """equal weights all assets"""
        #     weights = resample_data(price=price, freq=freq)
        #     weights[:] = 1 / len(price.columns)
            
        # elif method == "custom":
        #     """defined weights each assets"""
        #     weights = resample_data(price=price, freq=freq)
        #     weights[:] = np.nan
        #     for key, value in custom_weight.items():
        #         weights[key] = value
                
        # elif method == "target_vol":
        #     weights = TargetVol().simulate(price=price)

        # elif method == "abs_mmt":
        #     weights = AbsoluteMomentum().simulate(price=price)

        # elif method == "dual_mmt":
        #     weights = DualMomentum().simulate(price=price)

        # elif method == "dual_mmt2":
        #     weights = DualMomentum2().simulate(price=price)

        # elif method == "weighted_mmt":
        #     weights = WeightedMomentum().simulate(price=price)
        
        # elif method == "meb_mmt":
        #     weights = MebFaberMomentum().simulate(price=price)
        
        # elif method == "GTAA":
            
        #     weights = GTAA().simulate(price=price)
            
        # elif method == "VAA_agg":

        #     weights = VAA().aggressive_vaa(
        #         price=price, 
        #         offensive=offensive, 
        #         defensive=defensive
        #     )
            
        return weights
            
            
    def result(
        self,
        price: pd.DataFrame,
        weight: pd.DataFrame,
        start: ... = None,
        end: ... = None,
    ) -> pd.DataFrame:
        
        weight, nav, metrics = backtest_result(
            weight=weight,
            price=price,
            strategy_name=self.strategy_name,
            start_date=start,
            end_date=end    
        )
        
        merge = pd.concat(nav.values(), axis=1)
        merge.columns = nav.keys()
        nav = merge.fillna(method='ffill')
        
        mg_metrics = pd.concat(metrics.values(), axis=1)
        mg_metrics.columns = metrics.keys()
        mg_metrics = mg_metrics.T.reset_index().rename(columns={'index': 'strategy'})
        
        return weight, nav, mg_metrics


    # def report(
    #     self,
    #     nav: pd.DataFrame,
    #     start: ... = None,
    #     end: ... = None
    # ):
    #     nav_slice = nav.loc[start:end]
    #     nav_slice = nav_slice.pct_change().add(1).cumprod() * 1000
        
    #     result = result_metrics(nav=nav_slice)

    #     return result