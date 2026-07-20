"""
Insight-Invest FastAPI Application

데이터는 qdata S3 미러(KR 전 종목·US ETF·FRED)와 app/ parquet 계층
(meta·US 아카이브·포트폴리오)에서 읽는다 — DB·ETL 없음 (재구조 2026-07).

- 로컬 실행: uvicorn app.main:app --reload  (QDATA_LAKE·APP_DATA를 로컬 경로로 주면 오프라인 동작)
- Lambda 실행: handler = Mangum(app) — Function URL 뒤에서 서빙
- 인증: API_TOKEN 환경변수 설정 시 X-API-Key 헤더 필수 (공개 Function URL 보호)
"""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import backtest, meta, news, optimization, price, regime

app = FastAPI(
    title="Insight-Invest API",
    description="Investment analysis and backtesting API",
    version="3.0.0",
)

origins = [
    "http://localhost:3000",  # Local development
    "https://insight-invest-ten.vercel.app",  # Production frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_token(request: Request, call_next):
    token = os.environ.get("API_TOKEN", "")
    open_paths = {"/", "/health"}
    if token and request.url.path not in open_paths and request.method != "OPTIONS":
        if request.headers.get("x-api-key") != token:
            return JSONResponse(status_code=401, content={"detail": "invalid or missing API key"})
    return await call_next(request)


app.include_router(meta.router)
app.include_router(price.router)
app.include_router(backtest.router)
app.include_router(regime.router)
app.include_router(news.router)
app.include_router(optimization.router)


@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {"status": "healthy", "service": "insight-invest-api", "version": "3.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


try:  # Lambda 전용 — 로컬 uvicorn 실행에는 mangum이 없어도 된다
    from mangum import Mangum

    handler = Mangum(app)
except ImportError:
    handler = None
