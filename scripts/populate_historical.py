"""Populate historical IBJA gold rates."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date
from app.storage import get_storage
from app.config import settings

# Historical IBJA 916 PM rates (Rs/10g)
# Source: Official IBJA PDF (30Days.pdf) + user-provided earlier December data
HISTORICAL_DATA = [
    # (date, ibja_rate)
    # Earlier December 2025 data (user-provided)
    (date(2025, 12, 1), 115957),
    (date(2025, 12, 2), 117981),
    (date(2025, 12, 5), 117106),
    (date(2025, 12, 9), 117483),
    (date(2025, 12, 10), 117224),
    (date(2025, 12, 11), 117054),
    (date(2025, 12, 12), 117794),
    (date(2025, 12, 16), 122056),
    (date(2025, 12, 19), 121346),
    (date(2025, 12, 22), 120710),
    # From official IBJA PDF (Dec 23 onwards)
    (date(2025, 12, 23), 124835),
    (date(2025, 12, 24), 125150),
    # Dec 25 - Market Holiday
    (date(2025, 12, 26), 126368),
    # Dec 27-28 - Weekend
    (date(2025, 12, 29), 125291),
    (date(2025, 12, 30), 123293),
    (date(2025, 12, 31), 122007),
    # January 2026 data (from official IBJA PDF)
    (date(2026, 1, 1), 122250),
    (date(2026, 1, 2), 123460),
    # Jan 3-4 - Weekend
    (date(2026, 1, 5), 124730),
    (date(2026, 1, 6), 125181),
    (date(2026, 1, 7), 125194),
    (date(2026, 1, 8), 124368),
    (date(2026, 1, 9), 125604),
    # Jan 10-11 - Weekend
    (date(2026, 1, 12), 128651),
    (date(2026, 1, 13), 128500),
    (date(2026, 1, 14), 130086),
    # Jan 15 - Market Holiday (Election)
    (date(2026, 1, 16), 129699),
    # Jan 17-18 - Weekend
    (date(2026, 1, 19), 131855),
    (date(2026, 1, 20), 135027),
    (date(2026, 1, 21), 141272),
    (date(2026, 1, 22), 138433),
    (date(2026, 1, 23), 141348),
    # Jan 24-25 - Weekend
    # Jan 26 - Market Holiday (Republic Day)
    (date(2026, 1, 27), 145553),
    (date(2026, 1, 28), 150806),
]


def main():
    storage = get_storage()
    gst_rate = settings.GST_RATE  # 0.03 (3%)

    print(f"Populating {len(HISTORICAL_DATA)} historical records...")
    print(f"GST Rate: {gst_rate * 100}%")
    print("-" * 60)

    for rate_date, ibja_rate in HISTORICAL_DATA:
        rate_with_gst = round(ibja_rate * (1 + gst_rate), 2)
        storage.store_rate(rate_date, ibja_rate, rate_with_gst)
        print(f"{rate_date}: IBJA Rs {ibja_rate:,} -> With GST Rs {rate_with_gst:,.2f}")

    print("-" * 60)
    print(f"Done! Total records in DB: {storage.get_rate_count()}")

    # Show latest rate
    latest = storage.get_latest_rate()
    if latest:
        print(f"Latest rate: {latest['date']} - Rs {latest['rate_with_gst']:,.2f}")


if __name__ == "__main__":
    main()
