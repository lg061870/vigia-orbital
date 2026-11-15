"""Bring the daily table up to today with the newest NASA data, for live forecasts.

- NASA FIRMS VIIRS NOAA-20 near-real-time detections (the 2026 reference satellite),
  available within hours. Needs a FIRMS MAP_KEY.
- NASA POWER daily weather for the canton seats. POWER publishes with a lag of a few days,
  so weather (and MODIS vegetation, which lags weeks) is taken from the newest day available.

Only the standard library is used for HTTP and point-in-polygon, so this runs anywhere the API runs.
"""
from __future__ import annotations

import io
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np
import pandas as pd

POWER_VARS = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "WS2M", "GWETTOP"]
CARRY = ["vi_date", "ndvi_mean", "nbr_mean", "vi_valid_share", "ndmi_date", "ndmi_mean", "oni_anomaly",
         "elevation_m", "slope_deg", "northness", "eastness"]
BBOX = "-86.2,9.6,-84.6,11.3"          # Guanacaste with margin


def _get(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------- NASA POWER
def fetch_power(points: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Daily POWER weather per canton seat. points: columns canton, lat, lon."""
    def one(p):
        url = ("https://power.larc.nasa.gov/api/temporal/daily/point?"
               f"parameters={','.join(POWER_VARS)}&community=AG&longitude={p.lon}&latitude={p.lat}"
               f"&start={start:%Y%m%d}&end={end:%Y%m%d}&format=JSON")
        par = json.loads(_get(url))["properties"]["parameter"]
        return [{"canton": p.canton, "date": pd.Timestamp(d), **{k: par[k][d] for k in POWER_VARS}}
                for d in par["T2M"]]
    with ThreadPoolExecutor(6) as ex:
        rows = [r for part in ex.map(one, points.itertuples(index=False)) for r in part]
    df = pd.DataFrame(rows).replace(-999.0, np.nan)
    return df.dropna(subset=["T2M_MAX"])


# ---------------------------------------------------------------- NASA FIRMS
def _in_ring(x: np.ndarray, y: np.ndarray, ring: list) -> np.ndarray:
    r = np.asarray(ring)
    inside = np.zeros(len(x), bool)
    x1, y1 = r[:-1, 0], r[:-1, 1]
    x2, y2 = r[1:, 0], r[1:, 1]
    for a, b, c, d in zip(x1, y1, x2, y2):
        cond = ((b > y) != (d > y)) & (x < (c - a) * (y - b) / (d - b + 1e-15) + a)
        inside ^= cond
    return inside


def assign_canton(lon: np.ndarray, lat: np.ndarray, cantons_geojson: dict) -> np.ndarray:
    out = np.full(len(lon), None, object)
    for f in cantons_geojson["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        hit = np.zeros(len(lon), bool)
        for poly in polys:
            for ring in poly:                # even-odd rule handles holes
                hit ^= _in_ring(lon, lat, ring)
        out[hit & (out == None)] = f["properties"]["canton_id"]  # noqa: E711
    return out


def fetch_firms_noaa20(key: str, start: date, end: date, cantons_geojson: dict) -> pd.DataFrame:
    """VIIRS NOAA-20 NRT detections in Guanacaste, as rows shaped like the `detection` table."""
    frames, d = [], start
    while d <= end:
        n = min(5, (end - d).days + 1)
        txt = _get(f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_NOAA20_NRT/{BBOX}/{n}/{d}").decode()
        if not txt.startswith("latitude"):
            raise RuntimeError("FIRMS: " + txt[:80])
        frames.append(pd.read_csv(io.StringIO(txt), dtype={"acq_time": str}))
        d += timedelta(days=n)
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return pd.DataFrame(columns=["source", "processing", "type", "acq_datetime_utc", "canton_id"])
    df["acq_datetime_utc"] = pd.to_datetime(df.acq_date + " " + df.acq_time.str.zfill(4), format="%Y-%m-%d %H%M")
    df["canton_id"] = assign_canton(df.longitude.to_numpy(), df.latitude.to_numpy(), cantons_geojson)
    df = df.drop_duplicates(subset=["latitude", "longitude", "acq_datetime_utc"])
    return pd.DataFrame({"source": "viirs-jpss1", "processing": "NRT", "type": np.nan,
                         "acq_datetime_utc": df.acq_datetime_utc, "canton_id": df.canton_id,
                         "latitude": df.latitude, "longitude": df.longitude}).dropna(subset=["canton_id"])


# ---------------------------------------------------------------- extend the tables to today
def extend(cdd: pd.DataFrame, det: pd.DataFrame, today: pd.Timestamp,
           power: pd.DataFrame | None, firms: pd.DataFrame | None, firms_start: pd.Timestamp | None):
    """Return canton_day and detection tables extended to `today` with the new NASA data.

    New days get the newest POWER weather where it exists (left empty otherwise) and carry
    forward the last vegetation/terrain values. NOAA-20 detections from `firms_start` on are
    replaced by the freshly downloaded ones.
    """
    gte = cdd[cdd.canton_id.str.startswith("CR5")]
    last = gte.sort_values("date").groupby("canton_id").tail(1)
    days = pd.date_range(gte.date.max() + pd.Timedelta(days=1), today, freq="D")
    new = pd.DataFrame([{"canton_id": r.canton_id, "canton": r.canton, "date": d, **{c: r[c] for c in CARRY}}
                        for _, r in last.iterrows() for d in days])
    cdd2 = pd.concat([cdd, new], ignore_index=True) if len(new) else cdd.copy()
    if power is not None and len(power):
        p = power.set_index(["canton", "date"])[POWER_VARS]
        idx = pd.MultiIndex.from_frame(cdd2[["canton", "date"]])
        has = idx.isin(p.index)
        vals = p.reindex(idx[has])
        for v in POWER_VARS:
            cdd2.loc[has, v] = vals[v].to_numpy()
    det2 = det
    if firms is not None and firms_start is not None:
        local = det.acq_datetime_utc - pd.Timedelta(hours=6)
        keep = ~((det.source == "viirs-jpss1") & (local >= firms_start))
        firms = firms[firms.acq_datetime_utc - pd.Timedelta(hours=6) >= firms_start]
        det2 = pd.concat([det[keep], firms], ignore_index=True)
    return cdd2, det2
