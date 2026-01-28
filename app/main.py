"""FastAPI web application for Gold Investment Timing Optimizer."""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import date, datetime
from typing import Optional
import os

from app.config import settings
from app.storage import get_storage
from app.recommender import get_recommendation, get_current_context

# Initialize FastAPI app
app = FastAPI(
    title="Gold Investment Timing Optimizer",
    description="Helps optimize monthly gold investment timing with BUY/WAIT recommendations",
    version="1.0.0"
)

# Setup templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page with price input form."""
    context = get_current_context()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "context": context}
    )


@app.post("/check", response_class=HTMLResponse)
async def check_price(request: Request, price: float = Form(...)):
    """Process price and return recommendation."""
    if price < 1000 or price > 50000:
        raise HTTPException(
            status_code=400,
            detail="Price must be between 1000 and 50000 Rs/gram"
        )

    result = get_recommendation(price)
    today = date.today()

    return templates.TemplateResponse(
        "result.html",
        {"request": request, "result": result, "today": today}
    )


@app.get("/api/status")
async def api_status():
    """Get current status and metrics as JSON. Also serves as health check."""
    storage = get_storage()
    context = get_current_context()
    latest = storage.get_latest_rate()

    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "today": date.today().isoformat(),
        "day_of_month": context.day_of_month,
        "phase": context.phase,
        "phase_name": context.phase_name,
        "days_remaining": context.days_remaining,
        "metrics": {
            "reference_price": context.reference_price,
            "moving_average_20d": context.moving_average,
            "month_low": context.month_low,
            "month_high": context.month_high,
            "latest_ibja_with_gst": context.latest_ibja_rate,
        },
        "latest_rate": {
            "date": latest["date"] if latest else None,
            "ibja_rate": latest["ibja_rate"] if latest else None,
            "rate_with_gst": latest["rate_with_gst"] if latest else None,
        } if latest else None,
        "total_rates_stored": storage.get_rate_count()
    })


@app.get("/api/history")
async def api_history(
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get price history as JSON.

    Args:
        days: Number of days to return (default 30, ignored if dates provided)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    storage = get_storage()
    today = date.today()

    if start_date and end_date:
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD."
            )
    else:
        from datetime import timedelta
        end = today
        start = today - timedelta(days=days)

    rates = storage.get_rates_range(start, end)

    return JSONResponse({
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "count": len(rates),
        "rates": rates
    })


@app.get("/api/recommend")
async def api_recommend(price: float):
    """Get recommendation as JSON API.

    Args:
        price: Jeweller's quoted price per gram (with GST)
    """
    if price < 1000 or price > 50000:
        raise HTTPException(
            status_code=400,
            detail="Price must be between 1000 and 50000 Rs/gram"
        )

    result = get_recommendation(price)

    return JSONResponse({
        "recommendation": result.recommendation.value,
        "reason": result.reason,
        "confidence": result.confidence,
        "phase": result.phase,
        "day_of_month": result.day_of_month,
        "price": result.price,
        "reference_price": result.reference_price,
        "moving_average": result.moving_average,
        "month_low": result.month_low
    })


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}
