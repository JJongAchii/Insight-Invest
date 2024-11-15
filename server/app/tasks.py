import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../..")))

from celery_app import celery_app
from module.update_price import update_daily_price

@celery_app.task
def update_daily_price_task(market: str):
    update_daily_price(market)
