"""
Daily Screener Indicators Calculation Job.

Calculates technical indicators for all stocks and stores them in TbScreenerIndicators.
Run this after market close via scheduled job.

Usage:
    python -m module.screener.calculate_indicators --iso-code US
    python -m module.screener.calculate_indicators --iso-code KR
    python -m module.screener.calculate_indicators  # All countries
"""

import argparse
import logging
from datetime import date
from typing import List, Optional

import db
from module.backtest import Backtest
from sqlalchemy import delete, select

from .indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


def get_all_meta(iso_code: Optional[str] = None) -> List[db.TbMeta]:
    """Get all stock metadata."""
    with db.session_local() as session:
        stmt = select(db.TbMeta)
        if iso_code:
            stmt = stmt.where(db.TbMeta.iso_code == iso_code)
        results = session.execute(stmt).scalars().all()
        return list(results)


def calculate_and_store_indicators(iso_code: str, batch_size: int = 100) -> int:
    """
    Calculate indicators for all stocks in a country and store to DB.

    Args:
        iso_code: Country code (US or KR)
        batch_size: Number of stocks to process at once

    Returns:
        Number of stocks processed
    """
    logger.info(f"Starting indicator calculation for {iso_code}")

    # Get all stocks for this country
    stocks = get_all_meta(iso_code)
    if not stocks:
        logger.warning(f"No stocks found for {iso_code}")
        return 0

    meta_ids = [s.meta_id for s in stocks]
    ticker_meta = {s.ticker: s.meta_id for s in stocks}

    logger.info(f"Found {len(meta_ids)} stocks for {iso_code}")

    # Fetch price data for all stocks
    logger.info("Fetching price data...")
    bt = Backtest()
    price_df = bt.data(meta_id=meta_ids)

    if price_df.empty:
        logger.error(f"No price data available for {iso_code}")
        return 0

    logger.info(f"Loaded price data: {price_df.shape[0]} rows, {price_df.shape[1]} columns")

    # Calculate indicators
    logger.info("Calculating indicators...")
    indicators = TechnicalIndicators(price_df, ticker_meta)
    results = indicators.calculate_all()

    logger.info(f"Calculated indicators for {len(results)} stocks")

    if not results:
        logger.warning("No indicator results to store")
        return 0

    # Store to database
    today = date.today()
    records_to_upsert = []

    for result in results:
        records_to_upsert.append(
            {
                "meta_id": result.meta_id,
                "calculated_date": today,
                "current_price": result.current_price,
                "return_1m": result.return_1m,
                "return_3m": result.return_3m,
                "return_6m": result.return_6m,
                "return_12m": result.return_12m,
                "return_ytd": result.return_ytd,
                "volatility_1m": result.volatility_1m,
                "volatility_3m": result.volatility_3m,
                "mdd": result.mdd,
                "mdd_1y": result.mdd_1y,
                "current_drawdown": result.current_drawdown,
                "high_52w": result.high_52w,
                "low_52w": result.low_52w,
                "pct_from_high": result.pct_from_high,
                "pct_from_low": result.pct_from_low,
            }
        )

    # Batch upsert
    logger.info(f"Storing {len(records_to_upsert)} records to database...")

    with db.session_local() as session:
        # Delete existing records for these meta_ids
        meta_ids_to_update = [r["meta_id"] for r in records_to_upsert]
        session.execute(
            delete(db.TbScreenerIndicators).where(
                db.TbScreenerIndicators.meta_id.in_(meta_ids_to_update)
            )
        )

        # Insert new records
        for i in range(0, len(records_to_upsert), batch_size):
            batch = records_to_upsert[i : i + batch_size]
            session.execute(
                db.TbScreenerIndicators.__table__.insert(),
                batch,
            )
            logger.info(
                f"Inserted batch {i // batch_size + 1}/{(len(records_to_upsert) + batch_size - 1) // batch_size}"
            )

        session.commit()

    logger.info(f"Successfully stored indicators for {len(records_to_upsert)} stocks")
    return len(records_to_upsert)


def run_calculation(iso_code: Optional[str] = None) -> None:
    """
    Run indicator calculation for specified country or all countries.

    Args:
        iso_code: Country code (US, KR) or None for all
    """
    if iso_code:
        countries = [iso_code]
    else:
        countries = ["US", "KR"]

    total = 0
    for country in countries:
        try:
            count = calculate_and_store_indicators(country)
            total += count
            logger.info(f"Completed {country}: {count} stocks")
        except Exception as e:
            logger.error(f"Failed to calculate indicators for {country}: {e}", exc_info=True)

    logger.info(f"Total stocks processed: {total}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Calculate screener indicators")
    parser.add_argument(
        "--iso-code",
        type=str,
        choices=["US", "KR"],
        help="Country code to process (default: all)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    run_calculation(args.iso_code)


if __name__ == "__main__":
    main()
