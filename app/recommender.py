"""BUY/WAIT recommendation engine with adaptive phased strategy."""

from datetime import date
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from app.config import settings
from app.storage import get_storage


class Recommendation(Enum):
    BUY = "BUY"
    WAIT = "WAIT"


@dataclass
class RecommendationResult:
    """Result of a buy/wait recommendation."""
    recommendation: Recommendation
    reason: str
    phase: int
    day_of_month: int
    price: float
    reference_price: Optional[float]
    moving_average: Optional[float]
    month_low: Optional[float]
    confidence: str  # "high", "medium", "low"


@dataclass
class MarketContext:
    """Current market context for display."""
    today: date
    day_of_month: int
    phase: int
    phase_name: str
    reference_price: Optional[float]
    moving_average: Optional[float]
    month_low: Optional[float]
    month_high: Optional[float]
    latest_ibja_rate: Optional[float]
    days_remaining: int


def _get_phase(day: int) -> tuple[int, str]:
    """Determine current phase based on day of month."""
    if day <= settings.OBSERVATION_DAYS:
        return 1, "Observation"
    elif day <= settings.OPPORTUNISTIC_END:
        return 2, "Opportunistic"
    else:
        return 3, "Deadline"


def _calculate_percentage_diff(price: float, reference: float) -> float:
    """Calculate percentage difference from reference."""
    return (price - reference) / reference


def get_recommendation(price: float, check_date: date = None) -> RecommendationResult:
    """Get BUY/WAIT recommendation for given price.

    Args:
        price: Jeweller's quoted price per gram (with GST)
        check_date: Date to check (defaults to today)

    Returns:
        RecommendationResult with recommendation and reasoning
    """
    if check_date is None:
        check_date = date.today()

    storage = get_storage()
    day = check_date.day
    phase, phase_name = _get_phase(day)

    # Get reference data
    reference_price = storage.get_last_month_reference(check_date)
    moving_average = storage.get_moving_average(check_date)
    month_low = storage.get_month_low(check_date)

    # Handle missing reference data - use current price as fallback
    if reference_price is None:
        reference_price = price
    if moving_average is None:
        moving_average = price
    if month_low is None:
        month_low = price

    # Calculate differentials
    diff_from_ref = _calculate_percentage_diff(price, reference_price)
    diff_from_ma = _calculate_percentage_diff(price, moving_average)
    diff_from_low = _calculate_percentage_diff(price, month_low)

    # Phase 1: Observation (Days 1-10)
    # WAIT unless exceptional drop
    if phase == 1:
        is_exceptional = (
            diff_from_ref <= -settings.EXCEPTIONAL_DROP_THRESHOLD and
            diff_from_ma <= -settings.EXCEPTIONAL_MA_THRESHOLD
        )

        if is_exceptional:
            return RecommendationResult(
                recommendation=Recommendation.BUY,
                reason=f"Exceptional opportunity! Price is {abs(diff_from_ref)*100:.1f}% below reference "
                       f"and {abs(diff_from_ma)*100:.1f}% below moving average.",
                phase=phase,
                day_of_month=day,
                price=price,
                reference_price=reference_price,
                moving_average=moving_average,
                month_low=month_low,
                confidence="high"
            )
        else:
            return RecommendationResult(
                recommendation=Recommendation.WAIT,
                reason=f"Observation phase (Day {day}/10). Monitoring market trends. "
                       f"Price is {diff_from_ref*100:+.1f}% vs reference.",
                phase=phase,
                day_of_month=day,
                price=price,
                reference_price=reference_price,
                moving_average=moving_average,
                month_low=month_low,
                confidence="medium"
            )

    # Phase 2: Opportunistic (Days 11-22)
    # BUY only if ALL conditions met
    elif phase == 2:
        below_reference = diff_from_ref < 0
        near_month_low = diff_from_low <= settings.NEAR_MONTH_LOW_TOLERANCE
        below_ma = diff_from_ma < 0

        if below_reference and near_month_low and below_ma:
            return RecommendationResult(
                recommendation=Recommendation.BUY,
                reason=f"Good buying opportunity! Price is {abs(diff_from_ref)*100:.1f}% below reference, "
                       f"near month low ({diff_from_low*100:+.1f}%), and below MA.",
                phase=phase,
                day_of_month=day,
                price=price,
                reference_price=reference_price,
                moving_average=moving_average,
                month_low=month_low,
                confidence="high"
            )
        else:
            reasons = []
            if not below_reference:
                reasons.append(f"above reference ({diff_from_ref*100:+.1f}%)")
            if not near_month_low:
                reasons.append(f"not near month low ({diff_from_low*100:+.1f}%)")
            if not below_ma:
                reasons.append(f"above MA ({diff_from_ma*100:+.1f}%)")

            return RecommendationResult(
                recommendation=Recommendation.WAIT,
                reason=f"Opportunistic phase (Day {day}). Waiting for better price. "
                       f"Current price is {', '.join(reasons)}.",
                phase=phase,
                day_of_month=day,
                price=price,
                reference_price=reference_price,
                moving_average=moving_average,
                month_low=month_low,
                confidence="medium"
            )

    # Phase 3: Deadline (Days 23+)
    # Progressive relaxation - must buy by month end
    else:
        days_remaining = 31 - day  # Approximate
        urgency = max(0, min(1, (day - settings.DEADLINE_START) / 8))

        # Relaxed thresholds based on urgency
        relaxed_ref_threshold = 0.02 * (1 - urgency)  # Starts at 2%, goes to 0%
        relaxed_low_tolerance = settings.NEAR_MONTH_LOW_TOLERANCE * (1 + urgency * 2)

        near_reference = diff_from_ref <= relaxed_ref_threshold
        near_month_low = diff_from_low <= relaxed_low_tolerance

        # Day 28+: Must buy
        if day >= 28:
            return RecommendationResult(
                recommendation=Recommendation.BUY,
                reason=f"Month ending soon (Day {day}). Must complete monthly purchase. "
                       f"Price is {diff_from_ref*100:+.1f}% vs reference.",
                phase=phase,
                day_of_month=day,
                price=price,
                reference_price=reference_price,
                moving_average=moving_average,
                month_low=month_low,
                confidence="medium"
            )

        if near_reference or near_month_low:
            return RecommendationResult(
                recommendation=Recommendation.BUY,
                reason=f"Deadline phase (Day {day}). Acceptable price found. "
                       f"Price is {diff_from_ref*100:+.1f}% vs reference, "
                       f"{diff_from_low*100:+.1f}% vs month low.",
                phase=phase,
                day_of_month=day,
                price=price,
                reference_price=reference_price,
                moving_average=moving_average,
                month_low=month_low,
                confidence="medium"
            )
        else:
            return RecommendationResult(
                recommendation=Recommendation.WAIT,
                reason=f"Deadline phase (Day {day}). Price still high "
                       f"({diff_from_ref*100:+.1f}% vs reference). "
                       f"~{days_remaining} days remaining to find better price.",
                phase=phase,
                day_of_month=day,
                price=price,
                reference_price=reference_price,
                moving_average=moving_average,
                month_low=month_low,
                confidence="low"
            )


def get_current_context(check_date: date = None) -> MarketContext:
    """Get current market context for display."""
    if check_date is None:
        check_date = date.today()

    storage = get_storage()
    day = check_date.day
    phase, phase_name = _get_phase(day)

    latest = storage.get_latest_rate()
    latest_rate = latest["rate_with_gst"] if latest else None

    return MarketContext(
        today=check_date,
        day_of_month=day,
        phase=phase,
        phase_name=phase_name,
        reference_price=storage.get_last_month_reference(check_date),
        moving_average=storage.get_moving_average(check_date),
        month_low=storage.get_month_low(check_date),
        month_high=storage.get_month_high(check_date),
        latest_ibja_rate=latest_rate,
        days_remaining=31 - day  # Approximate
    )
