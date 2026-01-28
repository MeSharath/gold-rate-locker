# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gold Investment Timing Optimizer - An automated agent that helps optimize monthly gold investment timing by:
1. Tracking IBJA 916 rates daily (with 3% GST) for trend analysis
2. Providing a web form where users enter their jeweller's actual price
3. Generating personalized BUY/WAIT recommendations based on an adaptive phased strategy

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (development)
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v

# Test individual modules
python -c "from app.scraper import fetch_ibja_rate; print(fetch_ibja_rate())"
python -c "from app.recommender import get_recommendation; print(get_recommendation(7180))"

# Run daily update script (normally triggered by cron)
python scripts/daily_update.py
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    RAILWAY.APP                          │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌───────────────────┐    ┌─────────────────────────────────┐
│   CRON JOB        │    │         WEB SERVER              │
│   (Daily 6 PM)    │    │     (Always running)            │
│                   │    │                                 │
│ • Scrape IBJA 916 │    │  GET  /        → Web form       │
│ • Add 3% GST      │    │  POST /check   → Recommendation │
│ • Store in SQLite │    │  GET  /api/status → JSON metrics│
│ • Send email      │    │  GET  /api/history → Price hist │
└───────────────────┘    └─────────────────────────────────┘
```

**Data Flow:**
- `scraper.py` fetches IBJA 916 PM rate from ibjarates.com, applies 3% GST
- `storage.py` persists to SQLite (`data/gold_rates.db`)
- `recommender.py` implements the phased buying strategy using stored reference data
- `notifier.py` sends daily email summaries via Gmail SMTP
- `main.py` serves the FastAPI web application

## Core Algorithm: Adaptive Phased Buying Strategy

The recommendation engine in `recommender.py` uses three reference points:
- `last_month_reference`: Average price of final 7 days of previous month
- `moving_average_20d`: Rolling 20-day average
- `month_low_so_far`: Lowest price observed in current month

**Three Phases:**

| Phase | Days | Behavior |
|-------|------|----------|
| Observation | 1-10 | WAIT (unless exceptional drop: >=3% below reference AND >=2% below MA) |
| Opportunistic | 11-22 | BUY only if ALL conditions met: below reference, near month low (0.5%), below MA |
| Deadline | 23+ | Progressively relaxed criteria; must buy by month end |

## Database Schema

```sql
-- Daily IBJA rates with GST
CREATE TABLE rates (
    id INTEGER PRIMARY KEY, date DATE UNIQUE,
    ibja_rate REAL, rate_with_gst REAL, created_at TIMESTAMP
);

-- Actual purchases made
CREATE TABLE purchases (
    id INTEGER PRIMARY KEY, date DATE,
    price REAL, amount_invested REAL, gold_acquired REAL, created_at TIMESTAMP
);

-- Monthly reference calculations
CREATE TABLE monthly_references (
    id INTEGER PRIMARY KEY, month TEXT UNIQUE,
    reference_price REAL, month_low REAL, month_high REAL, created_at TIMESTAMP
);
```

## Key Configuration (via environment or `app/config.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OBSERVATION_DAYS` | 10 | Length of Phase 1 |
| `OPPORTUNISTIC_END` | 22 | Last day of Phase 2 |
| `EXCEPTIONAL_DROP_THRESHOLD` | 0.03 | 3% drop triggers immediate buy |
| `NEAR_MONTH_LOW_TOLERANCE` | 0.005 | 0.5% tolerance for "near low" |
| `MOVING_AVERAGE_WINDOW` | 20 | Days for trend calculation |
| `GST_RATE` | 0.03 | GST applied to IBJA rate |

## Environment Variables Required

```bash
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=gmail_app_password
EMAIL_TO=recipient@email.com
APP_URL=https://your-app.railway.app
```

## Data Source

IBJA 916 rate from https://ibjarates.com (PM rate, 22K gold standard for Indian jewellery). We store `ibja_rate * 1.03` to match actual jeweller prices which include 3% GST.
