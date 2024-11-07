import os
import sys
import pandas as pd
from typing import Union, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../..")))
import db
from module.strategy import EqualWeight, DualMomentum
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
        
        if method == "eq":
            """equal weights all assets"""
            weights = EqualWeight().simulate(price=price)
            
        if method == "dual_mmt":
            weights = DualMomentum().simulate(price=price)
        
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
        nav = merge.ffill()
        
        mg_metrics = pd.concat(metrics.values(), axis=1)
        mg_metrics.columns = metrics.keys()
        mg_metrics = mg_metrics.T.reset_index().rename(columns={'index': 'strategy'})
        
        return weight, nav, mg_metrics

    def delete_backtest_result(self, strategy_name: str):
        
        backtest_result.delete_strategy(strategy_name)
        
    def clear_backtest_result(self):
        
        backtest_result.clear_strategies()