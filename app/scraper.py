"""IBJA gold rate scraper from ibjarates.com."""

import requests
from bs4 import BeautifulSoup
import re
import time
from typing import Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Custom exception for scraper operations."""
    pass


# Request headers to mimic browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

IBJA_URL = "https://ibjarates.com"


def _normalize_rate(value: float) -> float:
    """Normalize rate to per-gram format.

    IBJA rates may be displayed per-10g or per-gram.
    """
    if value > 50000:  # Per-10g format
        return value / 10
    return value


def _extract_rate_from_table(soup: BeautifulSoup) -> Optional[float]:
    """Try to extract 916 PM rate from rates table."""
    try:
        # Look for table with PM rates
        tables = soup.find_all("table")
        for table in tables:
            # Check if this table contains PM rates
            text = table.get_text().lower()
            if "916" in text or "22k" in text or "22 k" in text:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    row_text = " ".join(c.get_text().strip() for c in cells).lower()
                    # Look for PM/evening rate row with 916/22K
                    if ("pm" in row_text or "evening" in row_text) and ("916" in row_text or "22k" in row_text or "22 k" in row_text):
                        # Extract numeric values
                        for cell in cells:
                            cell_text = cell.get_text().strip()
                            # Remove commas and try to parse
                            cleaned = re.sub(r"[^\d.]", "", cell_text)
                            if cleaned and len(cleaned) >= 4:
                                try:
                                    value = float(cleaned)
                                    if 4000 < value < 200000:  # Reasonable gold rate range
                                        return _normalize_rate(value)
                                except ValueError:
                                    continue
    except Exception as e:
        logger.debug(f"Table extraction failed: {e}")
    return None


def _extract_rate_from_header(soup: BeautifulSoup) -> Optional[float]:
    """Try to extract rate from header/banner display."""
    try:
        # Common patterns for rate display
        rate_patterns = [
            r"(?:916|22k|22K|22 k|22 K)[^\d]*?(\d{1,2},?\d{3}(?:\.\d+)?)",
            r"(\d{1,2},?\d{3}(?:\.\d+)?)[^\d]*?(?:916|22k|22K)",
            r"gold[^\d]*?(\d{1,2},?\d{3}(?:\.\d+)?)",
        ]

        # Look in header, banner, or prominent display areas
        for selector in ["header", ".banner", ".rate", ".gold", "#rate", "[class*='rate']", "[class*='gold']"]:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text()
                for pattern in rate_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        value_str = match.group(1).replace(",", "")
                        try:
                            value = float(value_str)
                            if 4000 < value < 200000:
                                return _normalize_rate(value)
                        except ValueError:
                            continue
    except Exception as e:
        logger.debug(f"Header extraction failed: {e}")
    return None


def _extract_rate_from_hidden(soup: BeautifulSoup) -> Optional[float]:
    """Try to extract rate from hidden input fields."""
    try:
        # Look for hidden gold rate field
        hidden_fields = soup.find_all("input", {"type": "hidden"})
        for field in hidden_fields:
            field_id = field.get("id", "").lower()
            field_name = field.get("name", "").lower()
            if "gold" in field_id or "gold" in field_name or "hdngold" in field_id:
                value_str = field.get("value", "").replace(",", "")
                try:
                    value = float(value_str)
                    if 4000 < value < 200000:
                        return _normalize_rate(value)
                except ValueError:
                    continue
    except Exception as e:
        logger.debug(f"Hidden field extraction failed: {e}")
    return None


def _extract_rate_generic(soup: BeautifulSoup) -> Optional[float]:
    """Generic extraction looking for any gold rate pattern."""
    try:
        text = soup.get_text()
        # Look for patterns like "Rs. 7,123" or "7123.00"
        patterns = [
            r"Rs\.?\s*(\d{1,2},?\d{3}(?:\.\d+)?)",
            r"INR\s*(\d{1,2},?\d{3}(?:\.\d+)?)",
            r"(\d{1,2},?\d{3}(?:\.\d+)?)\s*(?:per\s*)?(?:gram|gm|g)\b",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                value_str = match.replace(",", "")
                try:
                    value = float(value_str)
                    # For 916/22K gold, per-gram rate should be ~7000-9000
                    if 4000 < value < 15000:
                        return value
                except ValueError:
                    continue
    except Exception as e:
        logger.debug(f"Generic extraction failed: {e}")
    return None


def fetch_ibja_rate(retries: int = 3) -> float:
    """Fetch current IBJA 916 PM rate with GST.

    Returns rate per gram with 3% GST applied.

    Raises:
        ScraperError: If rate cannot be fetched after retries.
    """
    last_error = None

    for attempt in range(retries):
        try:
            if attempt > 0:
                # Exponential backoff
                time.sleep(2 ** attempt)

            response = requests.get(IBJA_URL, headers=HEADERS, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Try extraction methods in priority order
            rate = None

            # 1. Try table extraction (most reliable)
            rate = _extract_rate_from_table(soup)
            if rate:
                logger.info(f"Rate extracted from table: {rate}")

            # 2. Try header/banner
            if not rate:
                rate = _extract_rate_from_header(soup)
                if rate:
                    logger.info(f"Rate extracted from header: {rate}")

            # 3. Try hidden field
            if not rate:
                rate = _extract_rate_from_hidden(soup)
                if rate:
                    logger.info(f"Rate extracted from hidden field: {rate}")

            # 4. Generic extraction
            if not rate:
                rate = _extract_rate_generic(soup)
                if rate:
                    logger.info(f"Rate extracted generically: {rate}")

            if rate:
                # Apply 3% GST
                rate_with_gst = rate * (1 + settings.GST_RATE)
                logger.info(f"IBJA rate: {rate}, with GST: {rate_with_gst:.2f}")
                return rate_with_gst

            last_error = ScraperError("Could not extract rate from page")

        except requests.RequestException as e:
            last_error = ScraperError(f"Request failed: {e}")
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
        except Exception as e:
            last_error = ScraperError(f"Unexpected error: {e}")
            logger.warning(f"Attempt {attempt + 1} failed unexpectedly: {e}")

    raise last_error or ScraperError("Failed to fetch IBJA rate")


def get_ibja_rate_raw() -> Optional[float]:
    """Fetch raw IBJA rate without GST (for display purposes)."""
    try:
        rate_with_gst = fetch_ibja_rate()
        return rate_with_gst / (1 + settings.GST_RATE)
    except ScraperError:
        return None
