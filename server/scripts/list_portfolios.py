"""
포트폴리오 목록 조회 스크립트
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import TbPortfolio


def list_portfolios():
    """모든 포트폴리오 조회"""
    portfolios = TbPortfolio.query_df()
    print("=== All Portfolios ===")
    print(portfolios.to_string())
    print(f"\nTotal: {len(portfolios)} portfolios")


if __name__ == "__main__":
    list_portfolios()
