import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from .routers import meta, price, backtest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../..")))
from module.update_price import update_daily_price

app = FastAPI()
scheduler = BackgroundScheduler()

origins = [
    "http://localhost:3000",  # 로컬 개발용
    "https://insight-invest-ten.vercel.app",  # 배포된 프론트엔드 도메인
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(price.router)
app.include_router(backtest.router)

@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(update_daily_price, 'cron', args=['US'], hour=13, minute=15)  # Runs daily at 2 AM
    scheduler.start()

@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()