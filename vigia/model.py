"""Vigía Orbital fire-risk model: shared by the notebook (training) and the system (daily forecast).

Two layers:
  * Training (offline, notebook): `prepare_daily` builds daily canton features over the whole history,
    `fit_params` estimates everything the forecast needs and returns it as a plain dict
    (save with `save_params`). Same formulas as notebook cells C08-C14 and C26.
  * Daily forecast (online, the system): `forecast` takes the latest data and the saved params and returns
    the 5-day cards with their drivers. Nothing is stored: it is recomputed on every request.

Model (one per lead day k = 1..5):
    logit P(fire on day t+k) = b0 + bH*H_norm_k + bV*V + bC*C + bF*fire7_z + bT*T
  H_norm_k  log-odds of fire on day t+k for this canton and ISO week in the training years ("average year")
  V         vegetation vs normal: mean of z(NDVI anomaly), z(NDMI anomaly), re-standardized (higher = greener)
  C         weather dryness vs normal: mean of z(days without rain), z(Tmax), z(wind), -z(RH), -z(soil wetness),
            -z(30-day rain) anomalies, re-standardized (higher = drier)
  fire7_z   fire detected by the reference satellite in the canton in the last 7 days (0/1), standardized
  T         mean slope of the canton (NASADEM), standardized
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

LEADS = (1, 2, 3, 4, 5)
FEATS = ["V", "C", "fuego_7d_z", "T"]
ANOM_VARS = ["ndvi_mean", "ndmi_mean", "RH2M", "T2M_MAX", "WS2M", "GWETTOP", "lluvia_30d", "dias_sin_lluvia"]
SOURCES = ["modis", "viirs-snpp", "viirs-jpss1", "viirs-jpss2"]
LEVELS = [(0.10, "Low"), (0.30, "Moderate"), (0.50, "High"), (0.70, "Very high"), (1.01, "Extreme")]


def level(p: float) -> str:
    """Risk level from the probability of fire on that day."""
    for upper, name in LEVELS:
        if p < upper:
            return name
    return LEVELS[-1][1]


# ---------------------------------------------------------------- features (C08-C13)
def prepare_daily(canton_day: pd.DataFrame, detection: pd.DataFrame) -> pd.DataFrame:
    """Daily Guanacaste canton table with fire counts and the raw inputs of the model.

    canton_day: rows of the `canton_day` view (or data/csv/canton_day.csv), parsed dates.
    detection:  rows of the `detection` table (or data/csv/detection.csv), acq_datetime_utc parsed.
    """
    cd = canton_day[canton_day.canton_id.str.startswith("CR5")].copy()
    fire = detection[(detection.type == 0) | (detection.processing == "NRT")].copy()
    fire = fire[fire.canton_id.str.startswith("CR5", na=False)]
    fire["date"] = (fire.acq_datetime_utc - pd.Timedelta(hours=6)).dt.normalize()   # UTC -> Costa Rica
    daily = fire.groupby(["canton_id", "date", "source"]).size().unstack(fill_value=0).reset_index()
    cd = cd.merge(daily, on=["canton_id", "date"], how="left")
    for s in SOURCES:
        cd[s] = cd[s].fillna(0).astype(int) if s in cd else 0
    # Reference satellite (consistent measure): S-NPP to 2025, NOAA-20 from 2026 (S-NPP ended Nov 2026)
    cd["fire_ref"] = cd["viirs-snpp"].where(cd.date.dt.year <= 2025, cd["viirs-jpss1"])
    cd["fire_ref_day"] = (cd.fire_ref > 0).astype(int)
    cd = cd.sort_values(["canton_id", "date"]).reset_index(drop=True)
    g = cd.groupby("canton_id")
    for k in LEADS:
        cd[f"Y{k}"] = g.fire_ref_day.shift(-k)
    dry = (cd.PRECTOTCORR <= 1).astype(int)
    cd["dias_sin_lluvia"] = dry.groupby([cd.canton_id, (~dry.astype(bool)).groupby(cd.canton_id).cumsum()]).cumsum()
    cd["lluvia_30d"] = g.PRECTOTCORR.transform(lambda s: s.rolling(30, min_periods=1).sum())
    cd["fuego_7d"] = (g.fire_ref_day.transform(lambda s: s.rolling(7, min_periods=1).sum()) > 0).astype(int)
    cd["semana"] = cd.date.dt.isocalendar().week.clip(upper=52).astype(int)
    cd["year"] = cd.date.dt.year
    return cd


def _z(s: pd.Series, mu: float, sd: float) -> pd.Series:
    return (s - mu) / sd


def apply_features(cd: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Anomalies vs normal, composite V/C/T and fire7_z, using the stored normals and scaling."""
    cd = cd.copy()
    normals = pd.DataFrame(params["normals"])
    cd = cd.merge(normals, on=["canton_id", "semana"], how="left", suffixes=("", "_normal"))
    for v in ANOM_VARS:
        cd[v + "_anom"] = cd[v] - cd[v + "_normal"]
    zs = params["zstats"]
    z = lambda c: _z(cd[c], *zs[c])  # noqa: E731
    cd["V_raw"] = (z("ndvi_mean_anom") + z("ndmi_mean_anom")) / 2
    cd["C_raw"] = (z("dias_sin_lluvia_anom") + z("T2M_MAX_anom") + z("WS2M_anom")
                   - z("RH2M_anom") - z("GWETTOP_anom") - z("lluvia_30d_anom")) / 6
    cd["T_raw"] = cd.slope_deg
    for k in ["V", "C", "T"]:
        cd[k] = _z(cd[k + "_raw"], *zs[k + "_raw"])
    cd["fuego_7d_z"] = _z(cd.fuego_7d, *zs["fuego_7d"])
    return cd


# ---------------------------------------------------------------- training (C12-C14, C26)
def _logit_clim(train: pd.DataFrame, ycol: str) -> tuple[pd.DataFrame, float]:
    clim = train.groupby(["canton_id", "semana"])[ycol].mean().clip(0.01, 0.99)
    lg = np.log(clim / (1 - clim)).rename("H_norm").reset_index()
    p0 = train[ycol].mean()
    return lg, float(np.log(p0 / (1 - p0)))


def fit_params(cd: pd.DataFrame, train_years: tuple[int, int] = (2012, 2025), exclude_year: int | None = None) -> dict:
    """Estimate all model parameters from `prepare_daily` output. Pure function: returns a dict."""
    import statsmodels.api as sm

    y0, y1 = train_years
    train_mask = cd.year.between(y0, y1)
    if exclude_year is not None:
        train_mask &= cd.year != exclude_year
    base = cd[train_mask]
    normals = base.groupby(["canton_id", "semana"])[ANOM_VARS].mean().add_suffix("_normal").reset_index()
    params = {"train_years": [y0, y1], "exclude_year": exclude_year,
              "normals": normals.to_dict(orient="list"), "zstats": {}, "levels": LEVELS, "leads": {}}

    tmp = cd.merge(normals, on=["canton_id", "semana"], how="left")
    for v in ANOM_VARS:
        tmp[v + "_anom"] = tmp[v] - tmp[v + "_normal"]
    stat = lambda c: [float(tmp.loc[train_mask, c].mean()), float(tmp.loc[train_mask, c].std())]  # noqa: E731
    for c in [v + "_anom" for v in ANOM_VARS] + ["fuego_7d"]:
        params["zstats"][c] = stat(c)
    zs = params["zstats"]
    z = lambda c: _z(tmp[c], *zs[c])  # noqa: E731
    tmp["V_raw"] = (z("ndvi_mean_anom") + z("ndmi_mean_anom")) / 2
    tmp["C_raw"] = (z("dias_sin_lluvia_anom") + z("T2M_MAX_anom") + z("WS2M_anom")
                    - z("RH2M_anom") - z("GWETTOP_anom") - z("lluvia_30d_anom")) / 6
    tmp["T_raw"] = tmp.slope_deg
    for k in ["V_raw", "C_raw", "T_raw"]:
        params["zstats"][k] = stat(k)

    feats = apply_features(cd, params)
    for k in LEADS:
        yk = f"Y{k}"
        dk = feats[train_mask].dropna(subset=FEATS + [yk])
        lg, fill = _logit_clim(dk, yk)
        tr = dk.merge(lg, on=["canton_id", "semana"], how="left").fillna({"H_norm": fill})
        m = sm.Logit(tr[yk].astype(int), sm.add_constant(tr[["H_norm"] + FEATS])).fit(disp=0)
        params["leads"][str(k)] = {"coef": {n: float(v) for n, v in m.params.items()},
                                   "h_norm": lg.to_dict(orient="list"), "h_fill": fill, "n_train": int(m.nobs)}
    return params


def save_params(params: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(params, ensure_ascii=False))


def load_params(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


# ---------------------------------------------------------------- daily forecast (not stored)
def forecast(cd: pd.DataFrame, params: dict, canton: str, eve: str | pd.Timestamp | None = None) -> pd.DataFrame:
    """5-day forecast issued on `eve` (default: latest day with complete data) for one canton.

    cd: output of `prepare_daily` (must include the eve and the 7 days before it).
    Returns one row per lead day: date, prob, level, normal_prob and the driver multipliers on the odds.
    """
    feats = apply_features(cd, params)
    rows = feats[feats.canton.eq(canton) | feats.canton_id.eq(canton)].dropna(subset=FEATS)
    eve = rows.date.max() if eve is None else pd.Timestamp(eve)
    x = rows[rows.date == eve]
    if x.empty:
        raise ValueError(f"No complete data for {canton} on {eve.date()}")
    x = x.iloc[0]
    out = []
    for k in LEADS:
        lp = params["leads"][str(k)]
        b = lp["coef"]
        hn = pd.DataFrame(lp["h_norm"])
        h = hn[(hn.canton_id == x.canton_id) & (hn.semana == x.semana)].H_norm
        h_norm = float(h.iloc[0]) if len(h) else lp["h_fill"]
        eta = b["const"] + b["H_norm"] * h_norm + sum(b[f] * float(x[f]) for f in FEATS)
        p = 1 / (1 + np.exp(-eta))
        out.append({"eve": eve.date(), "lead": k, "date": (eve + pd.Timedelta(days=k)).date(),
                    "prob": round(float(p), 3), "level": level(float(p)),
                    "normal_prob": round(float(1 / (1 + np.exp(-h_norm))), 3),
                    "x_weather": round(float(np.exp(b["C"] * x.C)), 2),
                    "x_vegetation": round(float(np.exp(b["V"] * x.V)), 2),
                    "x_recent_fire": round(float(np.exp(b["fuego_7d_z"] * x.fuego_7d_z)), 2)})
    return pd.DataFrame(out)


def forecast_now(cd: pd.DataFrame, params: dict, canton: str, today: str | pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    """5-day forecast issued on the evening of `today` (days today+1 … today+5).

    Recent fire (F) and the normal for the week (H) use `today`. Weather (C) and vegetation (V)
    come from the newest day with complete inputs, because NASA POWER publishes a few days late
    and MODIS composites weeks late: their anomalies are carried forward to `today`.
    Returns the forecast table and a dict with the dates of each input.
    """
    today = pd.Timestamp(today).normalize()
    feats = apply_features(cd, params)
    rows = feats[feats.canton.eq(canton) | feats.canton_id.eq(canton)]
    comp = rows[rows.date <= today].dropna(subset=FEATS)
    if comp.empty:
        raise ValueError(f"No complete data for {canton}")
    w = comp.iloc[-1]
    t = rows[rows.date == today]
    if t.empty:
        raise ValueError(f"No row for {canton} on {today.date()}")
    t = t.iloc[0]
    x = w.copy()
    x["fuego_7d_z"], x["semana"], x["date"] = t.fuego_7d_z, t.semana, today
    out = []
    for k in LEADS:
        lp = params["leads"][str(k)]
        b = lp["coef"]
        hn = pd.DataFrame(lp["h_norm"])
        h = hn[(hn.canton_id == x.canton_id) & (hn.semana == x.semana)].H_norm
        h_norm = float(h.iloc[0]) if len(h) else lp["h_fill"]
        eta = b["const"] + b["H_norm"] * h_norm + sum(b[f] * float(x[f]) for f in FEATS)
        p = 1 / (1 + np.exp(-eta))
        out.append({"eve": today.date(), "lead": k, "date": (today + pd.Timedelta(days=k)).date(),
                    "prob": round(float(p), 3), "level": level(float(p)),
                    "normal_prob": round(float(1 / (1 + np.exp(-h_norm))), 3),
                    "x_weather": round(float(np.exp(b["C"] * x.C)), 2),
                    "x_vegetation": round(float(np.exp(b["V"] * x.V)), 2),
                    "x_recent_fire": round(float(np.exp(b["fuego_7d_z"] * x.fuego_7d_z)), 2)})
    dt = lambda c: str(pd.Timestamp(w[c]).date()) if c in w and pd.notna(w[c]) else None  # noqa: E731
    info = {"weather_as_of": str(w.date.date()), "ndvi_composite": dt("vi_date"), "ndmi_composite": dt("ndmi_date"),
            "recent_fire_through": str(today.date())}
    return pd.DataFrame(out), info
