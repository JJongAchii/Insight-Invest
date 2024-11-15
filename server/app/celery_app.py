# celery_app.py

from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['tasks']
)

celery_app.conf.timezone = 'Asia/Seoul'  # 필요한 시간대로 설정하세요.

celery_app.conf.beat_schedule = {
    'update-price-everyday-at-2am': {
        'task': 'tasks.update_daily_price_task',
        'schedule': crontab(hour=12, minute=50),
        'args': ('US',),  # 필요한 시장 코드를 전달하세요.
    },
}