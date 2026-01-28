"""Shared pytest fixtures for Gold Investment Timing Optimizer tests."""

import pytest


@pytest.fixture
def sample_rates():
    """Sample rate data for testing."""
    return [
        {"date": "2024-01-15", "ibja_rate": 7000, "rate_with_gst": 7210},
        {"date": "2024-01-16", "ibja_rate": 7050, "rate_with_gst": 7261.5},
        {"date": "2024-01-17", "ibja_rate": 6950, "rate_with_gst": 7158.5},
        {"date": "2024-01-18", "ibja_rate": 7100, "rate_with_gst": 7313},
        {"date": "2024-01-19", "ibja_rate": 7020, "rate_with_gst": 7230.6},
    ]
