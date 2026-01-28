"""Tests for the storage module."""

import pytest
from datetime import date, timedelta
import os
import tempfile


class TestStorage:
    """Test cases for Storage class."""

    @pytest.fixture(autouse=True)
    def setup_storage(self):
        """Setup fresh storage for each test."""
        # Reset singleton before each test
        from app.storage import Storage
        Storage._instance = None

        # Create temp file
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        # Get storage with explicit path
        from app.storage import get_storage
        self.storage = get_storage(self.db_path)

        yield

        # Cleanup
        Storage._instance = None
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_store_and_retrieve_rate(self):
        """Test storing and retrieving a rate."""
        today = date.today()
        self.storage.store_rate(today, 7000, 7210)

        rate = self.storage.get_rate(today)
        assert rate is not None
        assert rate["ibja_rate"] == 7000
        assert rate["rate_with_gst"] == 7210

    def test_get_latest_rate(self):
        """Test getting the most recent rate."""
        today = date.today()
        yesterday = today - timedelta(days=1)

        self.storage.store_rate(yesterday, 7000, 7210)
        self.storage.store_rate(today, 7100, 7313)

        latest = self.storage.get_latest_rate()
        assert latest is not None
        assert latest["ibja_rate"] == 7100

    def test_get_moving_average(self):
        """Test moving average calculation."""
        today = date.today()

        # Add 10 days of rates
        for i in range(10):
            d = today - timedelta(days=i)
            self.storage.store_rate(d, 7000 + i * 10, 7210 + i * 10.3)

        ma = self.storage.get_moving_average(today, window=5)
        assert ma is not None
        # MA should be average of last 5 days' rate_with_gst

    def test_get_month_low(self):
        """Test getting month low."""
        today = date.today()
        first_of_month = today.replace(day=1)

        # Add rates with varying prices
        self.storage.store_rate(first_of_month, 7200, 7416)
        self.storage.store_rate(first_of_month + timedelta(days=1), 7000, 7210)  # Lowest
        self.storage.store_rate(first_of_month + timedelta(days=2), 7100, 7313)

        month_low = self.storage.get_month_low(today)
        assert month_low == 7210

    def test_get_month_high(self):
        """Test getting month high."""
        today = date.today()
        first_of_month = today.replace(day=1)

        self.storage.store_rate(first_of_month, 7200, 7416)  # Highest
        self.storage.store_rate(first_of_month + timedelta(days=1), 7000, 7210)
        self.storage.store_rate(first_of_month + timedelta(days=2), 7100, 7313)

        month_high = self.storage.get_month_high(today)
        assert month_high == 7416

    def test_record_purchase(self):
        """Test recording a purchase."""
        today = date.today()
        self.storage.record_purchase(today, 7300, 10000, 1.37)

        purchases = self.storage.get_purchases()
        assert len(purchases) == 1
        assert purchases[0]["price"] == 7300
        assert purchases[0]["amount_invested"] == 10000

    def test_update_monthly_reference(self):
        """Test storing monthly reference."""
        self.storage.update_monthly_reference("2024-01", 7150, 7000, 7300)

        # Verify it's stored (would need to query directly)
        # For now, just ensure no errors

    def test_rate_count(self):
        """Test getting rate count."""
        today = date.today()
        assert self.storage.get_rate_count() == 0

        self.storage.store_rate(today, 7000, 7210)
        assert self.storage.get_rate_count() == 1

        self.storage.store_rate(today - timedelta(days=1), 7100, 7313)
        assert self.storage.get_rate_count() == 2

    def test_upsert_rate(self):
        """Test that storing same date updates the rate."""
        today = date.today()

        self.storage.store_rate(today, 7000, 7210)
        self.storage.store_rate(today, 7100, 7313)  # Update

        rate = self.storage.get_rate(today)
        assert rate["ibja_rate"] == 7100
        assert self.storage.get_rate_count() == 1
