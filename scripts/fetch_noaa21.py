"""Fetch VIIRS NOAA-21 (JPSS-2) detections for Costa Rica, Mar 2023 - today.

Same method and columns as scripts/fetch_2026.py (FIRMS area API, clipped to
Costa Rica, SP where available then NRT). Label: source = 'viirs-jpss2'.
-> data/vigia_orbital_firms_costa_rica_noaa21_2023_2026.csv
"""
from datetime import date

import fetch_2026 as f

f.FIRMS_SOURCES = [
    ("VIIRS_NOAA21_SP", "viirs-jpss2", "SP", date(2023, 3, 1), date(2026, 7, 31)),
    ("VIIRS_NOAA21_NRT", "viirs-jpss2", "NRT", date(2026, 8, 1), f.END),
]
f.OUT_NAME = "vigia_orbital_firms_costa_rica_noaa21_2023_2026.csv"

if __name__ == "__main__":
    f.firms()
