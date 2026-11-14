"""Fetch 2026 data (1 Jan 2026 to today) for Costa Rica / Guanacaste.

1. NASA FIRMS detections via the area API (needs env FIRMS_MAP_KEY), clipped to
   Costa Rica (geoBoundaries provinces). Standard processing (SP) where FIRMS has
   it, near-real-time (NRT) after that. Same unified columns as the 2012-2025 file,
   plus `processing` (SP / NRT). NRT rows have no `type` (left empty).
   -> data/vigia_orbital_firms_costa_rica_2026.csv
2. NASA POWER daily weather for the same 13 points as 2012-2025.
   -> data/nasa_power_guanacaste_daily_2026.csv
"""
import io
import json
import os
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
KEY = os.environ["FIRMS_MAP_KEY"]
BBOX = "-86.2,8.0,-82.5,11.3"
START = date(2026, 1, 1)
END = date.today()
# (FIRMS source id, our label, processing, first day, last day)
FIRMS_SOURCES = [
    ("MODIS_SP", "modis", "SP", START, date(2026, 8, 31)),
    ("MODIS_NRT", "modis", "NRT", date(2026, 9, 1), END),
    ("VIIRS_SNPP_SP", "viirs-snpp", "SP", START, date(2026, 7, 31)),
    ("VIIRS_SNPP_NRT", "viirs-snpp", "NRT", date(2026, 8, 1), END),
    ("VIIRS_NOAA20_SP", "viirs-jpss1", "SP", START, date(2026, 7, 31)),
    ("VIIRS_NOAA20_NRT", "viirs-jpss1", "NRT", date(2026, 8, 1), END),
]
COLS = ["source", "latitude", "longitude", "acq_date", "acq_time", "satellite", "instrument", "confidence",
        "frp", "daynight", "type", "bright_main", "bright_secondary", "scan", "track", "version", "processing"]
POWER_PARAMS = "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M,GWETTOP"


def get(url: str) -> bytes:
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return r.read()
        except Exception:
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(url.replace(KEY, "<KEY>"))


def firms() -> None:
    frames = []
    for src, label, proc, d0, d1 in FIRMS_SOURCES:
        d = d0
        while d <= d1:
            n = min(5, (d1 - d).days + 1)
            url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/{src}/{BBOX}/{n}/{d.isoformat()}"
            txt = get(url).decode()
            if txt.startswith("latitude"):
                df = pd.read_csv(io.StringIO(txt), dtype={"acq_time": str, "confidence": str, "version": str})
                if len(df):
                    df = df.rename(columns={"brightness": "bright_main", "bright_t31": "bright_secondary",
                                            "bright_ti4": "bright_main", "bright_ti5": "bright_secondary"})
                    df["source"], df["processing"] = label, proc
                    if "type" not in df:
                        df["type"] = pd.NA
                    frames.append(df)
            else:
                print("WARN", src, d, txt[:80])
            d += timedelta(days=n)
        print(src, "done", flush=True)
    df = pd.concat(frames, ignore_index=True)
    df["acq_time"] = df.acq_time.str.zfill(4)
    df = df.drop_duplicates(subset=["source", "latitude", "longitude", "acq_date", "acq_time"])
    prov = gpd.read_file(DATA / "costa_rica_provincias_geoboundaries.geojson")
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs=4326)
    inside = gpd.sjoin(pts, prov[["geometry"]], how="inner", predicate="within").index.unique()
    df = df.loc[inside].sort_values(["source", "acq_date", "acq_time"])[COLS]
    out = DATA / "vigia_orbital_firms_costa_rica_2026.csv"
    df.to_csv(out, index=False)
    print(out.name, len(df), "rows;", df.groupby(["source", "processing"]).size().to_dict())


def power() -> None:
    pts = pd.read_csv(DATA / "nasa_power_guanacaste_daily_2012_2025.csv",
                      usecols=["canton", "lat", "lon"]).drop_duplicates("canton")
    rows = []
    for _, p in pts.iterrows():
        url = ("https://power.larc.nasa.gov/api/temporal/daily/point?"
               f"parameters={POWER_PARAMS}&community=AG&longitude={p.lon}&latitude={p.lat}"
               f"&start={START:%Y%m%d}&end={END:%Y%m%d}&format=JSON")
        par = json.loads(get(url))["properties"]["parameter"]
        for day in par["T2M"]:
            d = pd.Timestamp(day)
            rows.append({"canton": p.canton, "lat": p.lat, "lon": p.lon, "YEAR": d.year, "DOY": d.dayofyear,
                         **{k: par[k][day] for k in POWER_PARAMS.split(",")}})
    df = pd.DataFrame(rows).replace(-999.0, pd.NA)
    df = df.dropna(subset=["T2M"])  # POWER publishes with a lag of a few days
    out = DATA / "nasa_power_guanacaste_daily_2026.csv"
    df.to_csv(out, index=False)
    print(out.name, len(df), "rows; last day per point:",
          df.groupby("canton").DOY.max().min(), "(DOY)")


if __name__ == "__main__":
    firms()
    power()
