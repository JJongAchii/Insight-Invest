from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import meta, price, backtest

app = FastAPI()

origins = [
    "http://localhost:8000",  # 로컬 개발용
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