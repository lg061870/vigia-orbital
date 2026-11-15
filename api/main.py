"""Vigía Orbital forecast API.

Issues the 5-day fire-risk forecast on request with the official model parameters
(data/results/OFFICIAL_RUN.json) and the shared functions in vigia/model.py.

Live data: at most once an hour the API downloads the newest NASA FIRMS (VIIRS NOAA-20
near-real-time) detections and NASA POWER weather, so the default forecast is issued
for today. FIRMS needs the env var FIRMS_MAP_KEY; without it, recent fire comes from the
repository data only. Nothing is stored: every response is computed on request.

Run locally:  uvicorn api.main:app --reload     (docs at http://127.0.0.1:8000/docs)
"""
import json
import os
import sys
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
RAW = "https://raw.githubusercontent.com/lg061870/vigia-orbital/main/"


def _ensure(rel: str, refresh: bool = False) -> Path:
    """Local file, downloaded from the public repository if this deployment does not have it."""
    p = ROOT / rel
    if refresh or not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(RAW + rel, timeout=120) as r:
            p.write_bytes(r.read())
    return p


# Deployments that copied only some files (e.g. the Hugging Face Space) get the live-data module here.
_ensure("vigia/live.py")
try:
    from vigia.model import forecast_now  # noqa: F401
except ImportError:                       # an older copy of vigia/model.py: fetch the current one
    import importlib

    import vigia.model
    _ensure("vigia/model.py", refresh=True)
    importlib.reload(vigia.model)
from vigia import live  # noqa: E402
from vigia.model import LEVELS, forecast, forecast_now, load_params, prepare_daily  # noqa: E402,F811


OFFICIAL = json.loads(_ensure("data/results/OFFICIAL_RUN.json").read_text())
PARAMS = load_params(_ensure(OFFICIAL["path"] + "/model_params.json"))
CDD0 = pd.read_csv(_ensure("data/csv/canton_day.csv"), parse_dates=["date"])
DET0 = pd.read_csv(_ensure("data/csv/detection.csv"), parse_dates=["acq_datetime_utc"],
                   usecols=["source", "processing", "type", "acq_datetime_utc", "canton_id"])
CANTON_GEO = json.loads(_ensure("site/data/cantons.geojson").read_text())
POWER_POINTS = (pd.read_csv(_ensure("data/nasa_power_guanacaste_daily_2026.csv"), usecols=["canton", "lat", "lon"])
                .drop_duplicates("canton"))
POWER_POINTS = POWER_POINTS[POWER_POINTS.canton.isin(CDD0.canton.unique())]
DATA_END = CDD0[CDD0.canton_id.str.startswith("CR5")].date.max()

NAMES = {"Canas": "Cañas", "Tilaran": "Tilarán"}
CANTONS = (CDD0[CDD0.canton_id.str.startswith("CR5")][["canton_id", "canton"]]
           .drop_duplicates().sort_values("canton_id"))
REFRESH_SECONDS = 3600


def today_cr() -> pd.Timestamp:
    """Today's date in Costa Rica (UTC−6)."""
    return pd.Timestamp((datetime.now(timezone.utc) - timedelta(hours=6)).date())


class State:
    """Daily table extended with the newest NASA data; refreshed at most once an hour."""
    lock = threading.Lock()
    daily = prepare_daily(CDD0, DET0)
    today = DATA_END
    refreshed = 0.0
    sources: dict = {"mode": "repository data only"}
    fire_through = DATA_END

    @classmethod
    def get(cls):
        if time.time() - cls.refreshed > REFRESH_SECONDS:
            with cls.lock:
                if time.time() - cls.refreshed > REFRESH_SECONDS:
                    cls._refresh()
        return cls.daily, cls.today

    @classmethod
    def _refresh(cls):
        today = today_cr()
        src = {"checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        power = firms = None
        try:
            power = live.fetch_power(POWER_POINTS, (DATA_END - pd.Timedelta(days=45)).date(), today.date())
            src["nasa_power"] = f"ok, weather through {power.date.max().date()}"
        except Exception as e:  # keep serving with what we have
            src["nasa_power"] = f"unavailable ({type(e).__name__})"
        key = os.environ.get("FIRMS_MAP_KEY")
        firms_start = DATA_END - pd.Timedelta(days=2)
        if key:
            try:
                firms = live.fetch_firms_noaa20(key, firms_start.date(), today.date(), CANTON_GEO)
                src["nasa_firms"] = f"ok, VIIRS NOAA-20 NRT through {today.date()} ({len(firms)} detections in Guanacaste since {firms_start.date()})"
            except Exception as e:
                src["nasa_firms"] = f"unavailable ({type(e).__name__})"
        else:
            src["nasa_firms"] = "no FIRMS_MAP_KEY set: recent fire from repository data only"
        cdd, det = live.extend(CDD0, DET0, today, power, firms, firms_start if firms is not None else None)
        cls.fire_through = today if firms is not None else DATA_END
        cls.daily, cls.today, cls.sources, cls.refreshed = prepare_daily(cdd, det), today, src, time.time()


app = FastAPI(
    title="Vigía Orbital API",
    description="5-day fire-risk forecast for the cantons of Guanacaste, Costa Rica, from harmonized NASA "
                "MODIS/VIIRS hot spots, NASA POWER weather and MODIS vegetation indices. By default the forecast "
                "is issued today with the newest NASA data (refreshed hourly). NASA Space Apps 2026. "
                "Research prototype, not an official warning.",
    version=OFFICIAL["run_id"],
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def _resolve(canton: str) -> tuple[str, str]:
    key = canton.strip().lower()
    for cid, name in CANTONS.itertuples(index=False):
        if key in (cid.lower(), name.lower(), NAMES.get(name, name).lower()):
            return cid, NAMES.get(name, name)
    raise HTTPException(404, f"Unknown canton '{canton}'. See /cantons.")


def _conditions(daily: pd.DataFrame, cid: str, day: str) -> dict:
    x = daily[(daily.canton_id == cid) & (daily.date == pd.Timestamp(day))].iloc[0]
    r = lambda v, n=1: None if pd.isna(v) else round(float(v), n)  # noqa: E731
    return {"date": day, "t_max_c": r(x.T2M_MAX), "t_min_c": r(x.T2M_MIN), "humidity_pct": r(x.RH2M, 0),
            "wind_kmh": r(x.WS2M * 3.6), "rain_mm": r(x.PRECTOTCORR), "days_without_rain": int(x.dias_sin_lluvia),
            "ndvi": r(x.ndvi_mean, 2), "ndmi": r(x.ndmi_mean, 2)}


def _run(cid: str, eve: date | None) -> tuple[pd.DataFrame, dict]:
    daily, today = State.get()
    try:
        if eve is None or pd.Timestamp(eve) >= daily[daily.T2M_MAX.notna()].date.max():
            f, info = forecast_now(daily, PARAMS, cid, today if eve is None else pd.Timestamp(eve))
            info["live"] = State.sources
            info["recent_fire_through"] = str(min(State.fire_through, pd.Timestamp(info["recent_fire_through"])).date())
        else:
            f = forecast(daily, PARAMS, cid, eve)
            e = str(f.eve.iloc[0])
            info = {"weather_as_of": e, "vegetation_as_of": e, "recent_fire_through": e}
    except ValueError as e:
        raise HTTPException(404, str(e))
    info["conditions"] = _conditions(daily, cid, info["weather_as_of"])
    # What the reference satellite saw afterwards, for dates already observed (None for the future)
    obs = daily[daily.canton_id == cid].set_index("date").fire_ref_day
    f["fire_observed"] = [int(obs[pd.Timestamp(d)]) if pd.Timestamp(d) in obs.index and pd.Timestamp(d) <= State.fire_through
                          else None for d in f.date]
    return f, info


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("docs")


@app.get("/health")
def health():
    daily, today = State.get()
    return {"status": "ok", "run_id": OFFICIAL["run_id"], "today": str(today.date()),
            "repository_data_until": str(DATA_END.date()), "live": State.sources}


@app.get("/cantons")
def cantons():
    return [{"canton_id": cid, "name": NAMES.get(n, n)} for cid, n in CANTONS.itertuples(index=False)]


@app.get("/model")
def model():
    """Official run: id, validation metrics, coefficients and risk levels."""
    return {"run_id": OFFICIAL["run_id"], "metrics": OFFICIAL["metrics"],
            "coefficients_5day": OFFICIAL["coefficients"],
            "coefficients_by_lead": {k: v["coef"] for k, v in PARAMS["leads"].items()},
            "levels": [{"below": u, "level": n} for u, n in LEVELS]}


@app.get("/forecast")
def forecast_one(canton: str = Query("Liberia", description="Canton name or id, e.g. Liberia or CR501"),
                 eve: date | None = Query(None, description="Issue date (the eve), YYYY-MM-DD. Default: today")):
    """5-day forecast for one canton issued on the evening of `eve` (default: today, with the newest NASA data)."""
    cid, name = _resolve(canton)
    f, info = _run(cid, eve)
    return {"canton_id": cid, "canton": name, "eve": str(f.eve.iloc[0]), "run_id": OFFICIAL["run_id"],
            "inputs": {k: v for k, v in info.items() if k not in ("conditions", "live")},
            "conditions": info["conditions"],
            "days": [{k: (str(v) if k == "date" else v) for k, v in r.items() if k != "eve"}
                     for r in f.to_dict("records")]}


@app.get("/forecast/all")
def forecast_all(eve: date | None = Query(None, description="Issue date (the eve), YYYY-MM-DD. Default: today")):
    """5-day forecast for every canton of Guanacaste."""
    out = [forecast_one(cid, eve) for cid in CANTONS.canton_id]
    return {"eve": out[0]["eve"], "run_id": OFFICIAL["run_id"], "inputs": out[0]["inputs"],
            "live": State.sources if eve is None else None, "cantons": out}


@app.get("/sms", response_class=PlainTextResponse)
def sms(canton: str = "Liberia", eve: date | None = None):
    """The forecast as a short text message for brigades (works with weak signal)."""
    cid, name = _resolve(canton)
    f, _ = _run(cid, eve)
    d0 = pd.Timestamp(f.eve.iloc[0])
    days = " · ".join(f"{pd.Timestamp(r.date):%a} {r.level}" for r in f.itertuples())
    top = f.loc[f.prob.idxmax()]
    return (f"FIRE RISK · {name.upper()}\nIssued {d0:%a %d %b %Y}\n{days}\n"
            f"Highest: {pd.Timestamp(top.date):%a} {top.level.upper()} ({round(top.prob * 100)} %)\nVigía Orbital")
