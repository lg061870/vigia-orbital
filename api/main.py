"""Vigía Orbital forecast API.

Computes the 5-day fire-risk forecast on request with the official model
parameters (data/results/OFFICIAL_RUN.json) and the shared functions in vigia/model.py.
Nothing is stored: every response is computed from the data and the parameters.

Run locally:  uvicorn api.main:app --reload     (docs at http://127.0.0.1:8000/docs)
"""
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vigia.model import LEVELS, forecast, load_params, prepare_daily  # noqa: E402

DATA = ROOT / "data"
OFFICIAL = json.loads((DATA / "results" / "OFFICIAL_RUN.json").read_text())
PARAMS = load_params(ROOT / OFFICIAL["path"] / "model_params.json")

_cdd = pd.read_csv(DATA / "csv" / "canton_day.csv", parse_dates=["date"])
_det = pd.read_csv(DATA / "csv" / "detection.csv", parse_dates=["acq_datetime_utc"], dtype={"version": str})
DAILY = prepare_daily(_cdd, _det)
del _cdd, _det
CANTONS = (DAILY[DAILY.canton_id.str.startswith("CR5")][["canton_id", "canton"]]
           .drop_duplicates().sort_values("canton_id"))
NAMES = {"Canas": "Cañas", "Tilaran": "Tilarán"}

app = FastAPI(
    title="Vigía Orbital API",
    description="5-day fire-risk forecast for the cantons of Guanacaste, Costa Rica, from harmonized NASA "
                "MODIS/VIIRS hot spots, NASA POWER weather and MODIS vegetation indices. NASA Space Apps 2026. "
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


def _forecast(cid: str, eve: date | None) -> pd.DataFrame:
    try:
        return forecast(DAILY, PARAMS, cid, eve)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/health")
def health():
    return {"status": "ok", "run_id": OFFICIAL["run_id"], "data_until": str(DAILY.date.max().date())}


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
                 eve: date | None = Query(None, description="Issue date (the eve), YYYY-MM-DD. Default: latest with data")):
    """5-day forecast for one canton issued on the evening of `eve`."""
    cid, name = _resolve(canton)
    f = _forecast(cid, eve)
    return {"canton_id": cid, "canton": name, "eve": str(f.eve.iloc[0]), "run_id": OFFICIAL["run_id"],
            "days": [{k: (str(v) if k == "date" else v) for k, v in r.items() if k != "eve"}
                     for r in f.to_dict("records")]}


@app.get("/forecast/all")
def forecast_all(eve: date | None = Query(None, description="Issue date (the eve), YYYY-MM-DD")):
    """5-day forecast for every canton of Guanacaste."""
    if eve is None:
        eve = DAILY.dropna(subset=["T2M_MAX", "ndvi_mean", "ndmi_mean"]).date.max().date()
    return {"eve": str(eve), "run_id": OFFICIAL["run_id"],
            "cantons": [forecast_one(cid, eve) for cid in CANTONS.canton_id]}


@app.get("/sms", response_class=PlainTextResponse)
def sms(canton: str = "Liberia", eve: date | None = None):
    """The forecast as a short text message for brigades (works with weak signal)."""
    cid, name = _resolve(canton)
    f = _forecast(cid, eve)
    d0 = pd.Timestamp(f.eve.iloc[0])
    days = " · ".join(f"{pd.Timestamp(r.date):%a} {r.level}" for r in f.itertuples())
    top = f.loc[f.prob.idxmax()]
    return (f"FIRE RISK · {name.upper()}\nIssued {d0:%a %d %b %Y}\n{days}\n"
            f"Highest: {pd.Timestamp(top.date):%a} {top.level.upper()} ({round(top.prob * 100)} %)\nVigía Orbital")
