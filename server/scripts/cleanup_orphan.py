"""
Orphan 포트폴리오 정리 스크립트
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import TbPortfolio, TbUniverse


def cleanup_orphan(port_name: str):
    """orphan 포트폴리오 삭제"""
    portfolio = TbPortfolio.query(port_name=port_name).first()

    if portfolio:
        port_id = portfolio.port_id
        print(f"Found orphan portfolio: port_id={port_id}, port_name={port_name}")

        # 관련 데이터 삭제
        TbUniverse.delete(port_id=port_id)
        TbPortfolio.delete(port_id=port_id)
        print("Deleted successfully")
    else:
        print(f"Portfolio '{port_name}' not found")


if __name__ == "__main__":
    port_name = sys.argv[1] if len(sys.argv) > 1 else "test_251214"
    cleanup_orphan(port_name)
