"""SQLite database operations for gold rate storage."""

import sqlite3
from datetime import datetime, date, timedelta
from typing import Optional, List, Tuple
from contextlib import contextmanager
import os

from app.config import settings


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


class Storage:
    """SQLite storage for gold rates and purchases."""

    _instance: Optional["Storage"] = None

    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return
        self.db_path = db_path or settings.DATABASE_PATH
        # Only create directory if db_path has a directory component
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()
        self._initialized = True

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"Database error: {e}") from e
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Daily IBJA rates with GST
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rates (
                    id INTEGER PRIMARY KEY,
                    date DATE UNIQUE,
                    ibja_rate REAL,
                    rate_with_gst REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Actual purchases made
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY,
                    date DATE,
                    price REAL,
                    amount_invested REAL,
                    gold_acquired REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Monthly reference calculations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monthly_references (
                    id INTEGER PRIMARY KEY,
                    month TEXT UNIQUE,
                    reference_price REAL,
                    month_low REAL,
                    month_high REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def store_rate(self, rate_date: date, ibja_rate: float, rate_with_gst: float) -> bool:
        """Store a daily rate. Returns True if new record, False if updated."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rates (date, ibja_rate, rate_with_gst)
                VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    ibja_rate = excluded.ibja_rate,
                    rate_with_gst = excluded.rate_with_gst
            """, (rate_date.isoformat(), ibja_rate, rate_with_gst))
            return cursor.rowcount > 0

    def get_rate(self, rate_date: date) -> Optional[dict]:
        """Get rate for a specific date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date, ibja_rate, rate_with_gst
                FROM rates WHERE date = ?
            """, (rate_date.isoformat(),))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_latest_rate(self) -> Optional[dict]:
        """Get the most recent rate."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date, ibja_rate, rate_with_gst
                FROM rates ORDER BY date DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_rates_range(self, start_date: date, end_date: date) -> List[dict]:
        """Get rates within a date range."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date, ibja_rate, rate_with_gst
                FROM rates
                WHERE date >= ? AND date <= ?
                ORDER BY date ASC
            """, (start_date.isoformat(), end_date.isoformat()))
            return [dict(row) for row in cursor.fetchall()]

    def get_moving_average(self, as_of_date: date, window: int = None) -> Optional[float]:
        """Calculate moving average of rate_with_gst for the past N days."""
        if window is None:
            window = settings.MOVING_AVERAGE_WINDOW

        start_date = as_of_date - timedelta(days=window)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT AVG(rate_with_gst) as avg_rate, COUNT(*) as count
                FROM rates
                WHERE date > ? AND date <= ?
            """, (start_date.isoformat(), as_of_date.isoformat()))
            row = cursor.fetchone()
            if row and row["count"] > 0:
                return row["avg_rate"]
            return None

    def get_last_month_reference(self, current_date: date) -> Optional[float]:
        """Get reference price from last month (average of final 7 days)."""
        # Calculate last month
        first_of_current = current_date.replace(day=1)
        last_of_prev = first_of_current - timedelta(days=1)
        start_of_final_week = last_of_prev - timedelta(days=6)

        # Check if we have it cached
        month_key = last_of_prev.strftime("%Y-%m")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT reference_price FROM monthly_references WHERE month = ?
            """, (month_key,))
            row = cursor.fetchone()
            if row and row["reference_price"]:
                return row["reference_price"]

        # Calculate from rates
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT AVG(rate_with_gst) as avg_rate, COUNT(*) as count
                FROM rates
                WHERE date >= ? AND date <= ?
            """, (start_of_final_week.isoformat(), last_of_prev.isoformat()))
            row = cursor.fetchone()
            if row and row["count"] > 0:
                return row["avg_rate"]
            return None

    def get_month_low(self, current_date: date) -> Optional[float]:
        """Get lowest rate_with_gst observed in current month."""
        first_of_month = current_date.replace(day=1)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MIN(rate_with_gst) as min_rate
                FROM rates
                WHERE date >= ? AND date <= ?
            """, (first_of_month.isoformat(), current_date.isoformat()))
            row = cursor.fetchone()
            if row:
                return row["min_rate"]
            return None

    def get_month_high(self, current_date: date) -> Optional[float]:
        """Get highest rate_with_gst observed in current month."""
        first_of_month = current_date.replace(day=1)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(rate_with_gst) as max_rate
                FROM rates
                WHERE date >= ? AND date <= ?
            """, (first_of_month.isoformat(), current_date.isoformat()))
            row = cursor.fetchone()
            if row:
                return row["max_rate"]
            return None

    def update_monthly_reference(self, month: str, reference_price: float,
                                  month_low: float, month_high: float):
        """Store or update monthly reference data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO monthly_references (month, reference_price, month_low, month_high)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(month) DO UPDATE SET
                    reference_price = excluded.reference_price,
                    month_low = excluded.month_low,
                    month_high = excluded.month_high
            """, (month, reference_price, month_low, month_high))

    def record_purchase(self, purchase_date: date, price: float,
                        amount_invested: float, gold_acquired: float):
        """Record a gold purchase."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO purchases (date, price, amount_invested, gold_acquired)
                VALUES (?, ?, ?, ?)
            """, (purchase_date.isoformat(), price, amount_invested, gold_acquired))

    def get_purchases(self, year: int = None, month: int = None) -> List[dict]:
        """Get purchase history, optionally filtered by year/month."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if year and month:
                month_str = f"{year}-{month:02d}"
                cursor.execute("""
                    SELECT date, price, amount_invested, gold_acquired
                    FROM purchases
                    WHERE strftime('%Y-%m', date) = ?
                    ORDER BY date ASC
                """, (month_str,))
            else:
                cursor.execute("""
                    SELECT date, price, amount_invested, gold_acquired
                    FROM purchases ORDER BY date ASC
                """)
            return [dict(row) for row in cursor.fetchall()]

    def get_rate_count(self) -> int:
        """Get total number of stored rates."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM rates")
            return cursor.fetchone()["count"]


# Convenience functions
def get_storage(db_path: str = None) -> Storage:
    """Get the storage singleton."""
    return Storage(db_path)
