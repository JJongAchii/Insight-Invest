# Legacy Price Updater Archive

## Date: 2025-12-14

## Reason for Archive
이 스크립트는 더 이상 사용되지 않습니다. 새로운 ETL 파이프라인으로 대체되었습니다.

## Replaced By
- `module/etl/daily_etl.py` - 새로운 ETL 파이프라인
- `run_scheduled_job.py` - ETL 스케줄러

## What Changed
1. `TbPrice` MySQL 테이블이 Iceberg로 이관됨
   - `market.us_stocks_price`
   - `market.kr_stocks_price`
2. 가격 데이터는 이제 Iceberg에서 읽음
   - `iceberg_client.read_price_data()`
   - `iceberg_client.get_latest_prices()`

## Files Archived
- `price.py` - 레거시 가격 업데이터 (TbPrice.insert() 사용)
