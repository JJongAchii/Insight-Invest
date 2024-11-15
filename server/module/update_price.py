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
    
    # Sort last_price by meta_id
    last_price = last_price.sort_values('meta_id').reset_index(drop=True)

    # Initialize an empty DataFrame to collect results if needed
    # all_merged_results = pd.DataFrame()

    # Get unique meta_ids and split into batches of 500
    meta_ids = last_price['meta_id'].unique()
    for i in range(0, len(meta_ids), 500):
        batch_meta_ids = meta_ids[i:i+500]
        batch_last_price = last_price[last_price['meta_id'].isin(batch_meta_ids)]
        
        # Process batch_last_price as before
        # Handle entries where max_dt is NaN (new tickers)
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
            new_data["gross_return"] = new_data.groupby("ticker")["adj_close"].pct_change()
            
            # Insert new data into the database
            db.TbPrice.insert(new_data)

        # Initialize a DataFrame to store results for this batch
        merged_results = pd.DataFrame()

        unique_dt = batch_last_price['max_dt'].unique()

        for date in unique_dt:
            if pd.notna(date):
                ticker_list = batch_last_price.loc[batch_last_price["max_dt"] == date, "ticker"].tolist()
                
                price = yf.download(tickers=ticker_list, start=date)
                
                # Adj Close 
                adj_price = price[["Adj Close"]]
                # Calculate returns
                returns = adj_price.div(adj_price.iloc[0]).dropna(axis=1).iloc[1:]
                returns.columns = returns.columns.droplevel(0)
                
                # Get last adj_close prices
                last_adj_close = batch_last_price.set_index("ticker")["adj_close"]
                # Multiply returns by last adj_close to get new adj_close
                mg_returns = returns.mul(last_adj_close, axis=1)
                mg_returns = mg_returns.stack(future_stack=True).reset_index().dropna()
                mg_returns.columns = ["trade_date", "ticker", "adj_close"]
                
                # Close prices
                cl_price = price[["Close"]].stack(future_stack=True).reset_index().dropna().iloc[1:]
                cl_price.columns = ["trade_date", "ticker", "close"]
                
                # Gross Return
                gross_return = price["Adj Close"].pct_change(fill_method=None).stack(future_stack=True).reset_index().dropna()
                gross_return.columns = ["trade_date", "ticker", "gross_return"]
    
                # Merge data
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
                
                # Append results
                merged_results = pd.concat([merged_results, mg_data], ignore_index=True)
        
        # Insert merged results for this batch into the database
        db.TbPrice.insert(merged_results)

        # Optionally, collect all results if needed
        # all_merged_results = pd.concat([all_merged_results, merged_results], ignore_index=True)
        
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