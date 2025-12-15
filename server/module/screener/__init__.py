"""
Stock Screener Module.

Provides technical indicator calculations and screening logic.

Usage:
    # Real-time calculation (for single stock)
    from module.screener import TechnicalIndicators, StockScreener

    # Pre-calculated indicators (for bulk screening)
    from module.screener.calculate_indicators import run_calculation
"""

from .indicators import TechnicalIndicators
from .screener import StockScreener

__all__ = ["TechnicalIndicators", "StockScreener"]
