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
from sqlalchemy import delete, inspect, select

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


def calculate_and_store_indicators(iso_code: str, batch_size: int = 500) -> int:
    """
    Calculate indicators for all stocks in a country and store to DB.

    Processes stocks in batches to avoid memory issues.

    Args:
        iso_code: Country code (US or KR)
        batch_size: Number of stocks to process at once (default: 500)

    Returns:
        Number of stocks processed
    """
    import gc

    logger.info(f"Starting indicator calculation for {iso_code}")

    # Get all stocks for this country
    stocks = get_all_meta(iso_code)
    if not stocks:
        logger.warning(f"No stocks found for {iso_code}")
        return 0

    logger.info(f"Found {len(stocks)} stocks for {iso_code}")

    # Process in batches to avoid OOM
    total_batches = (len(stocks) + batch_size - 1) // batch_size
    total_processed = 0
    today = date.today()

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(stocks))
        batch_stocks = stocks[start_idx:end_idx]

        logger.info(
            f"Processing batch {batch_idx + 1}/{total_batches} ({len(batch_stocks)} stocks)"
        )

        meta_ids = [s.meta_id for s in batch_stocks]
        ticker_meta = {s.ticker: s.meta_id for s in batch_stocks}

        try:
            # Fetch price data for this batch only
            bt = Backtest()
            price_df = bt.data(meta_id=meta_ids)

            if price_df.empty:
                logger.warning(f"No price data for batch {batch_idx + 1}")
                continue

            # Calculate indicators
            indicators = TechnicalIndicators(price_df, ticker_meta)
            results = indicators.calculate_all()

            if not results:
                logger.warning(f"No results for batch {batch_idx + 1}")
                continue

            # Build records (convert numpy types to Python native types)
            def to_python(val):
                """Convert numpy types to Python native types for PostgreSQL."""
                import numpy as np

                if val is None or (isinstance(val, float) and np.isnan(val)):
                    return None
                if hasattr(val, "item"):  # numpy scalar
                    return val.item()
                return val

            records = []
            for result in results:
                records.append(
                    {
                        "meta_id": result.meta_id,
                        "calculated_date": today,
                        "current_price": to_python(result.current_price),
                        "return_1m": to_python(result.return_1m),
                        "return_3m": to_python(result.return_3m),
                        "return_6m": to_python(result.return_6m),
                        "return_12m": to_python(result.return_12m),
                        "return_ytd": to_python(result.return_ytd),
                        "volatility_1m": to_python(result.volatility_1m),
                        "volatility_3m": to_python(result.volatility_3m),
                        "mdd": to_python(result.mdd),
                        "mdd_1y": to_python(result.mdd_1y),
                        "current_drawdown": to_python(result.current_drawdown),
                        "high_52w": to_python(result.high_52w),
                        "low_52w": to_python(result.low_52w),
                        "pct_from_high": to_python(result.pct_from_high),
                        "pct_from_low": to_python(result.pct_from_low),
                    }
                )

            # Store batch to database
            with db.session_local() as session:
                # Delete existing records for these meta_ids
                session.execute(
                    delete(db.TbScreenerIndicators).where(
                        db.TbScreenerIndicators.meta_id.in_(meta_ids)
                    )
                )
                # Insert new records
                session.execute(
                    db.TbScreenerIndicators.__table__.insert(),
                    records,
                )
                session.commit()

            total_processed += len(records)
            logger.info(f"Batch {batch_idx + 1}/{total_batches}: stored {len(records)} records")

            # Free memory
            del price_df, indicators, results, records
            gc.collect()

        except Exception as e:
            logger.error(f"Error in batch {batch_idx + 1}: {e}", exc_info=True)
            continue

    logger.info(f"Successfully stored indicators for {total_processed} stocks")
    return total_processed


def ensure_table_exists() -> None:
    """Create TbScreenerIndicators table if it doesn't exist."""
    from db.client import engine

    inspector = inspect(engine)
    if not inspector.has_table("tb_screener_indicators"):
        logger.info("Creating tb_screener_indicators table...")
        db.TbScreenerIndicators.__table__.create(engine)
        logger.info("Table created successfully")
    else:
        logger.info("tb_screener_indicators table already exists")


def run_calculation(iso_code: Optional[str] = None) -> None:
    """
    Run indicator calculation for specified country or all countries.

    Args:
        iso_code: Country code (US, KR) or None for all
    """
    # Ensure table exists before processing
    ensure_table_exists()

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
