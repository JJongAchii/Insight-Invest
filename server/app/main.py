"""
Insight-Invest FastAPI Application

This is a clean API server focused solely on serving HTTP endpoints.
Scheduled data updates are handled by separate AWS EventBridge Scheduled Jobs.

Architecture:
- API Server: Handles HTTP requests (this file)
- Scheduled Jobs: Separate ECS tasks triggered by EventBridge
  - us-price-updater: Updates US market data
  - kr-price-updater: Updates KR market data
  - macro-updater: Updates macroeconomic data
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import backtest, meta, regime

# Initialize FastAPI app
app = FastAPI(
    title="Insight-Invest API",
    description="Investment analysis and backtesting API",
    version="2.0.0",
)

# CORS configuration
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

# Include API routers
app.include_router(meta.router)
app.include_router(backtest.router)
app.include_router(regime.router)


@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {"status": "healthy", "service": "insight-invest-api", "version": "2.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer."""
    return {"status": "healthy"}
