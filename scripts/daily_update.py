#!/usr/bin/env python3
"""Daily update script for gold rate tracking.

This script is designed to be run by a cron job (e.g., daily at 6 PM IST).

Steps:
1. Scrape IBJA 916 PM rate
2. Apply GST and store in database
3. Update monthly reference if month changed
4. Send summary email (if configured)
"""

import sys
import os
from datetime import date, timedelta
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.scraper import fetch_ibja_rate, ScraperError
from app.storage import get_storage, DatabaseError
from app.notifier import send_daily_summary, is_email_configured

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def update_monthly_reference_if_needed(storage, today: date):
    """Update monthly reference if we're in a new month."""
    # Check if we need to calculate reference for previous month
    first_of_month = today.replace(day=1)
    if today.day <= 3:  # First few days of month, calculate prev month reference
        last_of_prev = first_of_month - timedelta(days=1)
        month_key = last_of_prev.strftime("%Y-%m")

        # Get rates for previous month
        first_of_prev = last_of_prev.replace(day=1)
        rates = storage.get_rates_range(first_of_prev, last_of_prev)

        if rates:
            # Calculate reference (average of final 7 days)
            final_week = rates[-7:] if len(rates) >= 7 else rates
            reference = sum(r["rate_with_gst"] for r in final_week) / len(final_week)
            month_low = min(r["rate_with_gst"] for r in rates)
            month_high = max(r["rate_with_gst"] for r in rates)

            storage.update_monthly_reference(month_key, reference, month_low, month_high)
            logger.info(f"Updated monthly reference for {month_key}: {reference:.2f}")


def main():
    """Main daily update routine."""
    today = date.today()
    logger.info(f"Starting daily update for {today}")

    storage = get_storage()
    errors = []

    # Step 1: Scrape IBJA rate
    try:
        rate_with_gst = fetch_ibja_rate()
        ibja_rate = rate_with_gst / (1 + settings.GST_RATE)
        logger.info(f"Fetched IBJA rate: {ibja_rate:.2f}, with GST: {rate_with_gst:.2f}")
    except ScraperError as e:
        logger.error(f"Failed to fetch IBJA rate: {e}")
        errors.append(f"Scraper: {e}")
        # Cannot continue without rate
        return 1

    # Step 2: Store rate
    try:
        storage.store_rate(today, ibja_rate, rate_with_gst)
        logger.info("Rate stored successfully")
    except DatabaseError as e:
        logger.error(f"Failed to store rate: {e}")
        errors.append(f"Storage: {e}")

    # Step 3: Update monthly reference if needed
    try:
        update_monthly_reference_if_needed(storage, today)
    except Exception as e:
        logger.error(f"Failed to update monthly reference: {e}")
        errors.append(f"Reference update: {e}")

    # Step 4: Send email summary (if configured)
    if is_email_configured():
        try:
            reference = storage.get_last_month_reference(today)
            ma = storage.get_moving_average(today)
            month_low = storage.get_month_low(today)

            success = send_daily_summary(
                rate_date=today,
                ibja_rate=ibja_rate,
                rate_with_gst=rate_with_gst,
                reference_price=reference,
                moving_average=ma,
                month_low=month_low
            )
            if success:
                logger.info("Daily summary email sent")
            else:
                logger.warning("Failed to send daily summary email")
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            errors.append(f"Email: {e}")
    else:
        logger.info("Email not configured, skipping notification")

    # Summary
    if errors:
        logger.warning(f"Daily update completed with {len(errors)} error(s)")
        for err in errors:
            logger.warning(f"  - {err}")
        return 1
    else:
        logger.info("Daily update completed successfully")
        return 0


if __name__ == "__main__":
    sys.exit(main())
