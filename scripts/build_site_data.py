"""Build the JSON files for the static website (site/data/) from the official run.

Uses the official model parameters (data/results/OFFICIAL_RUN.json -> model_params.json)
and vigia/model.py, so the site shows exactly what the notebook computed.

Outputs:
  site/data/cantons.geojson   Guanacaste cantons (simplified) with id, name, conservation area
  site/data/latest.json       5-day forecast from the latest eve with complete data, all cantons
  site/data/demo.json         5-day forecast from the eve of 18 Jan 2018, all cantons,
                              model trained WITHOUT 2018 (honest back-test), plus what happened
  site/data/meta.json         run id, metrics, sources
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vigia.model import fit_params, forecast, load_params, prepare_daily  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "site" / "data"
DEMO_EVE = "2018-01-18"


def conditions(daily: pd.DataFrame, canton_id: str, eve: pd.Timestamp) -> dict:
    x = daily[(daily.canton_id == canton_id) & (daily.date == eve)].iloc[0]
    r = lambda v, n=1: None if pd.isna(v) else round(float(v), n)  # noqa: E731
    return {"t_max_c": r(x.T2M_MAX), "t_min_c": r(x.T2M_MIN), "humidity_pct": r(x.RH2M, 0),
            "wind_kmh": r(x.WS2M * 3.6), "rain_mm": r(x.PRECTOTCORR), "days_without_rain": int(x.dias_sin_lluvia),
            "ndvi": r(x.ndvi_mean, 2), "ndmi": r(x.ndmi_mean, 2)}


def run_all(daily, params, eve, observed=False):
    cantons = daily[daily.canton_id.str.startswith("CR5")][["canton_id", "canton"]].drop_duplicates()
    out = {}
    for cid, name in cantons.itertuples(index=False):
        f = forecast(daily, params, cid, eve)
        days = []
        for _, d in f.iterrows():
            item = {"date": str(d.date), "prob": d.prob, "level": d.level, "normal_prob": d.normal_prob,
                    "x_weather": d.x_weather, "x_vegetation": d.x_vegetation, "x_recent_fire": d.x_recent_fire}
            if observed:
                row = daily[(daily.canton_id == cid) & (daily.date == pd.Timestamp(d.date))]
                item["fire_observed"] = int(row.fire_ref_day.iloc[0]) if len(row) else None
            days.append(item)
        out[cid] = {"name": name, "eve": str(f.eve.iloc[0]), "days": days,
                    "conditions": conditions(daily, cid, pd.Timestamp(f.eve.iloc[0]))}
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    official = json.loads((DATA / "results" / "OFFICIAL_RUN.json").read_text())
    run_dir = ROOT / official["path"]
    params = load_params(run_dir / "model_params.json")
    manifest = json.loads((run_dir / "manifest.json").read_text())

    cdd = pd.read_csv(DATA / "csv" / "canton_day.csv", parse_dates=["date"])
    det = pd.read_csv(DATA / "csv" / "detection.csv", parse_dates=["acq_datetime_utc"], dtype={"version": str})
    daily = prepare_daily(cdd, det)

    # Latest eve with complete inputs (same for all cantons)
    feats_ok = daily.dropna(subset=["T2M_MAX", "ndvi_mean", "ndmi_mean"])
    latest_eve = feats_ok.date.max()
    latest = run_all(daily, params, latest_eve)
    (OUT / "latest.json").write_text(json.dumps({"eve": str(latest_eve.date()), "cantons": latest}))

    params_wo = fit_params(daily, exclude_year=2018)       # honest back-test for the demo week
    demo = run_all(daily, params_wo, pd.Timestamp(DEMO_EVE), observed=True)
    (OUT / "demo.json").write_text(json.dumps({"eve": DEMO_EVE, "note": "Model trained without any 2018 data",
                                               "cantons": demo}))

    prov = gpd.read_file(DATA / "costa_rica_provincias_geoboundaries.geojson")
    cant = gpd.read_file(DATA / "costa_rica_cantones_geoboundaries.geojson")
    gte = prov.loc[prov.shapeISO == "CR-G"].geometry.union_all()
    cant = cant[cant.geometry.representative_point().within(gte)].copy()
    lut = pd.read_csv(DATA / "guanacaste_canton_area_conservacion.csv").set_index("canton")
    ids = daily[["canton", "canton_id"]].drop_duplicates().set_index("canton").canton_id
    names_es = {"Canas": "Cañas", "Tilaran": "Tilarán"}
    cant["canton_id"] = cant.shapeName.map(ids)
    cant["name"] = cant.shapeName.map(lambda n: names_es.get(n, n))
    cant["ac"] = cant.shapeName.map(lut.ac_abbr)
    cant["geometry"] = cant.to_crs(5367).geometry.simplify(150).to_crs(4326)
    cant[["canton_id", "name", "ac", "geometry"]].to_file(OUT / "cantons.geojson", driver="GeoJSON",
                                                          COORDINATE_PRECISION=5)

    meta = {"run_id": manifest["run_id"], "metrics": manifest["metrics"], "data_commit": manifest["repo_commit"],
            "latest_eve": str(latest_eve.date()), "demo_eve": DEMO_EVE,
            "levels": [[u, n] for u, n in params["levels"]]}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    for f in sorted(OUT.iterdir()):
        print(f"{f.name:18s} {f.stat().st_size/1e3:7.1f} KB")


if __name__ == "__main__" and "--fire-days" not in sys.argv:
    main()
    fire_days()


def fire_days() -> None:
    """site/data/fire_days.json: for each canton, the days with fire seen by the reference satellite.

    Lets the website show what happened after any past forecast without asking the API.
    Days are counted from 2012-01-01 to keep the file small.
    """
    cdd = pd.read_csv(DATA / "csv" / "canton_day.csv", parse_dates=["date"])
    det = pd.read_csv(DATA / "csv" / "detection.csv", parse_dates=["acq_datetime_utc"], dtype={"version": str})
    daily = prepare_daily(cdd, det)
    origin = pd.Timestamp("2012-01-01")
    out = {"origin": "2012-01-01", "through": str(daily.date.max().date()), "cantons": {}}
    for cid, g in daily[daily.fire_ref_day == 1].groupby("canton_id"):
        out["cantons"][cid] = [int(x) for x in (g.date - origin).dt.days]
    p = OUT / "fire_days.json"
    p.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{p.name:18s} {p.stat().st_size/1e3:7.1f} KB")


if __name__ == "__main__" and "--fire-days" in sys.argv:
    fire_days()
