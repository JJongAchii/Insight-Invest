# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Insight-Invest is an investment analysis and backtesting platform for US/Korean stock markets. It consists of a FastAPI backend, Next.js frontend, and AWS-deployed scheduled jobs for data updates.

## Common Commands

### Backend (server/)

```bash
# Install dependencies
cd server && pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/
pytest tests/test_backtest.py -v  # Single test file

# Code formatting (enforced by pre-commit hooks)
black --line-length=100 server/
isort --profile=black --line-length=100 server/
```

### Frontend (client/)

```bash
cd client
npm install
npm run dev      # Development server (localhost:3000)
npm run build    # Production build
npm run lint     # ESLint
```

### Pre-commit Hooks

Pre-commit is configured with Black, isort, hadolint, and YAML formatters. Run `pre-commit install` to set up hooks.

### AWS Copilot Deployment

```bash
# Deploy API server
copilot svc deploy --name api --env dev

# Deploy scheduled jobs
copilot job deploy --name us-price-updater --env dev
copilot job deploy --name kr-price-updater --env dev
copilot job deploy --name macro-updater --env dev

# View logs
copilot svc logs --name api --env dev --follow
copilot job logs --name us-price-updater --env dev --follow
```

## Architecture

### Backend Structure (server/)

- `app/main.py` - FastAPI application entry point
- `app/routers/` - API endpoints:
  - `meta.py` - Stock metadata endpoints
  - `price.py` - Price data endpoints
  - `backtest.py` - Backtesting endpoints
  - `regime.py` - Market regime analysis
- `module/` - Business logic:
  - `update_data/` - Data update logic (price, macro)
  - `backtest.py` - Backtesting engine
  - `metrics.py` - Portfolio performance calculations
  - `strategy.py` - Strategy definitions
  - `etl/` - ETL pipeline modules
  - `data_lake/` - Data lake integration
- `db/` - Database models (SQLAlchemy):
  - `TbMeta` - Stock metadata
  - `TbPrice` - Price history
  - `TbStrategy`, `TbPortfolio` - Strategy/portfolio definitions
  - `TbRebalance`, `TbNav`, `TbMetrics` - Backtest results
  - `TbMacro`, `TbMacroData` - Macroeconomic indicators
- `run_scheduled_job.py` - Entry point for scheduled ECS tasks

### Frontend Structure (client/src/)

- `app/` - Next.js 14 App Router pages:
  - `home/` - Dashboard home
  - `stocksearch/` - Stock search UI
  - `backtest/` - Backtesting interface
  - `regime/` - Market regime visualization
  - `(components)/` - Shared components (Navbar, Sidebar)
- `state/api.ts` - RTK Query API client (all backend API calls defined here)

### Infrastructure (copilot/)

AWS Copilot manages:
- `api/` - FastAPI service on ECS Fargate
- `us-price-updater/` - US market data update job (daily 18:00 KST)
- `kr-price-updater/` - KR market data update job (daily 06:00 KST)
- `macro-updater/` - FRED macro data update job (daily 08:00 KST)

### Data Flow

1. Scheduled jobs fetch data from yfinance (stocks) and FRED API (macro)
2. Data stored in PostgreSQL (RDS)
3. FastAPI serves data to Next.js frontend via RTK Query
4. Frontend deployed on Vercel, backend on AWS ECS

## Key Technologies

- **Backend**: FastAPI, SQLAlchemy 2.0, Pandas, NumPy, yfinance, fredapi
- **Frontend**: Next.js 14, TypeScript, Redux Toolkit (RTK Query), MUI, Tailwind CSS, Chart.js/Recharts
- **Infrastructure**: AWS ECS Fargate, RDS PostgreSQL, EventBridge, GitHub Actions CI/CD

## CI/CD

GitHub Actions (`.github/workflows/deploy.yml`) auto-deploys on push to `main` when `server/` or `copilot/` files change.
