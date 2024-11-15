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
    
    # Determine the batch size
    batch_size = 500
    num_records = last_price.shape[0]
    
    # Loop over the DataFrame in chunks of 500
    for start_idx in range(0, num_records, batch_size):
        end_idx = min(start_idx + batch_size, num_records)
        batch_last_price = last_price.iloc[start_idx:end_idx]

        # Process tickers with no max_dt (new entries)
        if batch_last_price["max_dt"].isna().any():
            ticker_list = batch_last_price.loc[batch_last_price["max_dt"].isna(), "ticker"].tolist()
            price = yf.download(tickers=ticker_list)[["Adj Close", "Close"]]
            price = price.stack(future_stack=True).reset_index().dropna()
            price.columns = ["trade_date", "ticker", "adj_close", "close"]
            
            new_data = pd.merge(
                price,
                batch_last_price[["meta_id", "ticker"]],
                on="ticker",
                how="left"
            )
            new_data["gross_return"] = new_data.groupby("ticker")["adj_close"].pct_change(fill_method=None)
    
            db.TbPrice.insert(new_data)

        # Initialize an empty DataFrame to collect results
        merged_results = pd.DataFrame()
    
        unique_dt = batch_last_price.max_dt.dropna().unique()
    
        for date in unique_dt:
            ticker_list = batch_last_price.loc[batch_last_price["max_dt"] == date, "ticker"].tolist()
            price = yf.download(tickers=ticker_list, start=date)
            
            # Adj Close 
            adj_price = price[["Adj Close"]]
            returns = adj_price.div(adj_price.iloc[0]).dropna(axis=1).iloc[1:]
            returns.columns = returns.columns.droplevel(0)
            
            mg_returns = returns.mul(
                batch_last_price.set_index("ticker")["adj_close"].squeeze()
            )
            mg_returns = mg_returns.stack(future_stack=True).reset_index().dropna()
            mg_returns.columns = ["trade_date", "ticker", "adj_close"]
            
            # Close
            cl_price = price[["Close"]].stack(future_stack=True).reset_index().dropna().iloc[1:]
            cl_price.columns = ["trade_date", "ticker", "close"]
            
            # Gross Return
            gross_return = price["Adj Close"].pct_change(fill_method=None).stack(future_stack=True).reset_index()
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
                batch_last_price[["meta_id", "ticker"]],
                on="ticker",
                how="left"
            )
            
            merged_results = pd.concat([merged_results, mg_data], ignore_index=True)
        
        # Insert the merged results for the current batch
        if not merged_results.empty:
            db.TbPrice.insert(merged_results)



if __name__ == "__main__":
    
    args = get_args()
    
    try:
        if args.script == "us_price":
            update_daily_price(market="US")
        elif args.script == "kr_price":
            update_daily_price(market="KR")
    except Exception as error:
        print(f"An error occurred: {error}")