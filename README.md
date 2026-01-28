# Gold Investment Timing Optimizer

A comprehensive automated agent designed to optimize monthly gold investment timing. This application tracks daily rates, analyzes trends, and provides personalized BUY/WAIT recommendations based on an adaptive phased strategy.

## Features

- **Daily Rate Tracking**: Automatically scrapes IBJA 916 rates daily (adding 3% GST) to build a historical price database.
- **Trend Analysis**: Calculates moving averages, monthly references, and identifies market phases.
- **Investment Recommendations**: Provides actionable BUY or WAIT advice based on a sophisticated phased strategy.
- **Web Interface**: A clean web form for users to check recommendations against their jeweller's actual price.
- **API Endpoints**: JSON endpoints for retrieving current status, historical data, and recommendations.
- **Email Notifications**: Daily email summaries with current rates and recommendations (configured via SMTP).

## Architecture

The system consists of two main components:
1. **Cron Job (Daily 6 PM)**: Scrapes rates, updates the database, and sends email notifications.
2. **Web Server**: Always-running FastAPI application serving the web interface and API.

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

## How It Works

The recommendation engine implements an **Adaptive Phased Buying Strategy** with three distinct phases each month:

| Phase | Days | Behavior |
|-------|------|----------|
| **Observation** | 1-10 | Generally recommends **WAIT**, unless an exceptional drop occurs (≥3% below reference AND ≥2% below 20-day MA). |
| **Opportunistic** | 11-22 | Recommends **BUY** only if strict conditions are met: price is below reference, near the month's low (within 0.5%), and below the 20-day MA. |
| **Deadline** | 23+ | Criteria progressively relax to ensure a purchase is made before month-end. |

The system uses three key reference points:
- **Last Month Reference**: Average price of the final 7 days of the previous month.
- **Moving Average (20d)**: Rolling 20-day average price.
- **Month Low**: The lowest price observed so far in the current month.

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file or set the following environment variables:
   ```bash
   SMTP_USER=your.email@gmail.com
   SMTP_PASSWORD=gmail_app_password
   EMAIL_TO=recipient@email.com
   APP_URL=http://localhost:8000
   ```

## Usage

### Running Locally

Start the web server:
```bash
uvicorn app.main:app --reload
```
Visit `http://localhost:8000` to access the web interface.

### Running Tests

Run the test suite with pytest:
```bash
pytest tests/ -v
```

### Manual Scripts

Update daily rates manually:
```bash
python scripts/daily_update.py
```

Test individual modules:
```bash
# Test scraper
python -c "from app.scraper import fetch_ibja_rate; print(fetch_ibja_rate())"

# Test recommender
python -c "from app.recommender import get_recommendation; print(get_recommendation(7180))"
```

## API Documentation

- **GET /**: Renders the home page with the price input form.
- **POST /check**: Processes a price submission and returns the recommendation page.
- **GET /api/status**: Returns current system status, metrics, and latest rates as JSON.
- **GET /api/history**: Returns historical price data.
  - Query Params: `days` (default 30), `start_date`, `end_date` (YYYY-MM-DD).
- **GET /api/recommend**: Returns recommendation data as JSON.
  - Query Param: `price` (float, required).

## Configuration

Key parameters can be configured in `app/config.py` or via environment variables:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OBSERVATION_DAYS` | 10 | Length of Phase 1 |
| `OPPORTUNISTIC_END` | 22 | Last day of Phase 2 |
| `EXCEPTIONAL_DROP_THRESHOLD` | 0.03 | Drop required for immediate buy in Phase 1 |
| `NEAR_MONTH_LOW_TOLERANCE` | 0.005 | Tolerance for "near low" calculation |
| `MOVING_AVERAGE_WINDOW` | 20 | Days for trend calculation |
| `GST_RATE` | 0.03 | GST applied to IBJA rate |

## Data Source

Rates are sourced from [IBJA Rates](https://ibjarates.com) (PM rate, 22K). The system stores `ibja_rate * 1.03` to reflect the actual market price including 3% GST.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
