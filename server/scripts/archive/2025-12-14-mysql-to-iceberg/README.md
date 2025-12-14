# MySQL to Iceberg Migration Scripts (Archived)

These scripts were used to migrate portfolio data from MySQL to Iceberg.

**Migration completed on**: 2025-12-14

## DO NOT RUN

These scripts will fail because `TbNav`, `TbRebalance`, `TbMetrics` models have been removed from `db/models.py`.

## Migrated Tables

| MySQL Table | Iceberg Table |
|-------------|---------------|
| `tb_nav` | `portfolio.portfolio_nav` |
| `tb_rebalance` | `portfolio.portfolio_rebalance` |
| `tb_metrics` | `portfolio.portfolio_metrics` |

## Data Access (New)

```python
from module.data_lake.portfolio_reader import (
    get_portfolio_nav,
    get_portfolio_rebalance,
    get_portfolio_metrics,
)

# NAV 조회
nav_df = get_portfolio_nav(port_id=1)

# Rebalance 조회
rebal_df = get_portfolio_rebalance(port_id=1)

# Metrics 조회
metrics_df = get_portfolio_metrics(port_id=1)
```

## Scripts in This Archive

- `migrate_portfolio_nav.py` - TbNav → Iceberg migration
- `migrate_portfolio_rebalance.py` - TbRebalance → Iceberg migration
- `migrate_portfolio_metrics.py` - TbMetrics → Iceberg migration

Keep for reference only.
