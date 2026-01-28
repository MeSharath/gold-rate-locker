"""Tests for the recommender module."""

import pytest
from datetime import date
from unittest.mock import patch, Mock


class TestRecommender:
    """Test cases for the recommendation engine."""

    def test_get_phase_observation(self):
        """Test phase detection for observation days."""
        from app.recommender import _get_phase

        phase, name = _get_phase(1)
        assert phase == 1
        assert name == "Observation"

        phase, name = _get_phase(10)
        assert phase == 1

    def test_get_phase_opportunistic(self):
        """Test phase detection for opportunistic days."""
        from app.recommender import _get_phase

        phase, name = _get_phase(11)
        assert phase == 2
        assert name == "Opportunistic"

        phase, name = _get_phase(22)
        assert phase == 2

    def test_get_phase_deadline(self):
        """Test phase detection for deadline days."""
        from app.recommender import _get_phase

        phase, name = _get_phase(23)
        assert phase == 3
        assert name == "Deadline"

        phase, name = _get_phase(30)
        assert phase == 3

    def test_percentage_diff_calculation(self):
        """Test percentage difference calculation."""
        from app.recommender import _calculate_percentage_diff

        # 5% increase
        diff = _calculate_percentage_diff(105, 100)
        assert diff == pytest.approx(0.05)

        # 3% decrease
        diff = _calculate_percentage_diff(97, 100)
        assert diff == pytest.approx(-0.03)

    @patch("app.recommender.get_storage")
    def test_phase1_wait_normal_conditions(self, mock_get_storage):
        """Test Phase 1 recommends WAIT under normal conditions."""
        from app.recommender import get_recommendation, Recommendation

        mock_storage = Mock()
        mock_storage.get_last_month_reference.return_value = 7200
        mock_storage.get_moving_average.return_value = 7150
        mock_storage.get_month_low.return_value = 7100
        mock_get_storage.return_value = mock_storage

        # Day 5, price at reference level
        result = get_recommendation(7200, date(2024, 1, 5))

        assert result.recommendation == Recommendation.WAIT
        assert result.phase == 1
        assert "Observation" in result.reason

    @patch("app.recommender.get_storage")
    def test_phase1_buy_exceptional_drop(self, mock_get_storage):
        """Test Phase 1 recommends BUY on exceptional drop."""
        from app.recommender import get_recommendation, Recommendation

        mock_storage = Mock()
        mock_storage.get_last_month_reference.return_value = 7500
        mock_storage.get_moving_average.return_value = 7400
        mock_storage.get_month_low.return_value = 7100
        mock_get_storage.return_value = mock_storage

        # Price is 5% below reference and 3% below MA
        result = get_recommendation(7100, date(2024, 1, 5))

        assert result.recommendation == Recommendation.BUY
        assert result.phase == 1
        assert "Exceptional" in result.reason

    @patch("app.recommender.get_storage")
    def test_phase2_buy_all_conditions_met(self, mock_get_storage):
        """Test Phase 2 recommends BUY when all conditions met."""
        from app.recommender import get_recommendation, Recommendation

        mock_storage = Mock()
        mock_storage.get_last_month_reference.return_value = 7300
        mock_storage.get_moving_average.return_value = 7250
        mock_storage.get_month_low.return_value = 7100
        mock_get_storage.return_value = mock_storage

        # Price below reference, at month low, below MA
        result = get_recommendation(7100, date(2024, 1, 15))

        assert result.recommendation == Recommendation.BUY
        assert result.phase == 2
        assert result.confidence == "high"

    @patch("app.recommender.get_storage")
    def test_phase2_wait_above_reference(self, mock_get_storage):
        """Test Phase 2 recommends WAIT when above reference."""
        from app.recommender import get_recommendation, Recommendation

        mock_storage = Mock()
        mock_storage.get_last_month_reference.return_value = 7200
        mock_storage.get_moving_average.return_value = 7150
        mock_storage.get_month_low.return_value = 7100
        mock_get_storage.return_value = mock_storage

        # Price above reference
        result = get_recommendation(7300, date(2024, 1, 15))

        assert result.recommendation == Recommendation.WAIT
        assert result.phase == 2
        assert "above reference" in result.reason

    @patch("app.recommender.get_storage")
    def test_phase3_must_buy_near_month_end(self, mock_get_storage):
        """Test Phase 3 forces BUY near month end."""
        from app.recommender import get_recommendation, Recommendation

        mock_storage = Mock()
        mock_storage.get_last_month_reference.return_value = 7200
        mock_storage.get_moving_average.return_value = 7150
        mock_storage.get_month_low.return_value = 7100
        mock_get_storage.return_value = mock_storage

        # Day 28, even if price is high
        result = get_recommendation(7400, date(2024, 1, 28))

        assert result.recommendation == Recommendation.BUY
        assert result.phase == 3
        assert "Month ending" in result.reason

    @patch("app.recommender.get_storage")
    def test_missing_reference_uses_current_price(self, mock_get_storage):
        """Test fallback to current price when reference data missing."""
        from app.recommender import get_recommendation, Recommendation

        mock_storage = Mock()
        mock_storage.get_last_month_reference.return_value = None
        mock_storage.get_moving_average.return_value = None
        mock_storage.get_month_low.return_value = None
        mock_get_storage.return_value = mock_storage

        # Should not crash, uses price as fallback
        result = get_recommendation(7200, date(2024, 1, 15))

        assert result.recommendation in [Recommendation.BUY, Recommendation.WAIT]

    @patch("app.recommender.get_storage")
    def test_get_current_context(self, mock_get_storage):
        """Test getting current market context."""
        from app.recommender import get_current_context

        mock_storage = Mock()
        mock_storage.get_last_month_reference.return_value = 7200
        mock_storage.get_moving_average.return_value = 7150
        mock_storage.get_month_low.return_value = 7100
        mock_storage.get_month_high.return_value = 7400
        mock_storage.get_latest_rate.return_value = {
            "date": "2024-01-15",
            "rate_with_gst": 7250
        }
        mock_get_storage.return_value = mock_storage

        context = get_current_context(date(2024, 1, 15))

        assert context.day_of_month == 15
        assert context.phase == 2
        assert context.phase_name == "Opportunistic"
        assert context.reference_price == 7200
        assert context.latest_ibja_rate == 7250
