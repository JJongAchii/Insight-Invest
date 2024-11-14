import os
import sys
import sqlalchemy as sa
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../..")))
import db
from config import get_args


def get_last_updated_price(market: str):
    with db.session_local() as session:
        subq = (
            session.query(
                db.TbPrice.meta_id,
                sa.func.max(db.TbPrice.trade_date).label("max_dt")
            )
            .group_by(db.TbPrice.meta_id)
        ).subquery()
        
        query = (
            session.query(
                db.TbMeta.meta_id,
                db.TbMeta.ticker,
                db.TbMeta.iso_code,
                subq.c.max_dt,
                db.TbPrice.adj_close,
            )
            .outerjoin(
                subq,
                subq.c.meta_id == db.TbMeta.meta_id
            )
            .outerjoin(
                db.TbPrice,
                sa.and_(
                    db.TbPrice.meta_id == db.TbMeta.meta_id,
                    db.TbPrice.trade_date == subq.c.max_dt
                )
            )
            .filter(db.TbMeta.iso_code == market)
        )
        
        data = db.read_sql_query(query=query)

    return data


def update_daily_price(market: str):
    last_price = get_last_updated_price(market=market)
    last_price.loc[last_price["iso_code"] == "KR", "ticker"] = last_price.ticker + ".KS"

    if last_price["max_dt"].isna().any():
        
        ticker_list = last_price.loc[last_price["max_dt"].isna(), "ticker"].tolist()
        price = yf.download(tickers=ticker_list)[["Adj Close", "Close"]]
        price = price.stack().reset_index().dropna()
        price.columns = ["trade_date", "ticker", "adj_close", "close"]
        
        new_data = pd.merge(
            price,
            last_price[["meta_id", "ticker"]],
            on="ticker",
            how="left"
        )
        new_data["gross_return"] = new_data.groupby("ticker")["adj_close"].pct_change()

        db.TbPrice.insert(new_data)

    merged_results = pd.DataFrame()

    unique_dt = last_price.max_dt.unique()

    for date in unique_dt:
        if date: 
            ticker_list = last_price.loc[last_price["max_dt"] == date, "ticker"].tolist()
            
            price = yf.download(tickers=ticker_list, start=date)
            
            # Adj Close 
            adj_price = price[["Adj Close"]]
            returns = adj_price.div(adj_price.iloc[0]).dropna(axis=1).iloc[1:]
            returns.columns = returns.columns.droplevel(0)
            
            mg_returns = returns.mul(
                last_price.set_index("ticker")["adj_close"].squeeze()
            )
            mg_returns = mg_returns.stack().reset_index().dropna()
            mg_returns.columns = ["trade_date", "ticker", "adj_close"]
            
            #Close
            cl_price = price[["Close"]].stack().reset_index().dropna().iloc[1:]
            cl_price.columns = ["trade_date", "ticker", "close"]
            
            #Gross Return
            gross_return = price["Adj Close"].pct_change().stack().reset_index()
            gross_return.columns = ["trade_date", "ticker", "gross_return"]

            mg_close = pd.merge(
                mg_returns,
                cl_price,
                on=["trade_date", "ticker"],
                how="left"
            )
            
            mg_gross = pd.merge(
                mg_close,
                gross_return,
                on=["trade_date", "ticker"],
                how="left"
            )
            
            mg_data = pd.merge(
                mg_gross,
                last_price[["meta_id", "ticker"]],
                on="ticker",
                how="left"
            )
            
            if merged_results.empty:
                merged_results = mg_data
            else:
                merged_results = pd.concat([merged_results, mg_data], ignore_index=True)
    
    db.TbPrice.insert(merged_results)
    
    return


if __name__ == "__main__":
    
    args = get_args()
    
    try:
        if args.script == "us_price":
            update_daily_price(market="US")
        elif args.script == "kr_price":
            update_daily_price(market="KR")
    except Exception as error:
        print(f"An error occurred: {error}")