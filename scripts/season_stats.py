"""Season-level numbers used in the pitch hook (all reproducible from data/).

Season = calendar year (the Guanacaste dry season peaks Feb-Apr). Robustness
checks: a Nov-Oct season year, and MODIS / NOAA-20 instead of VIIRS S-NPP.
ENSO index = ONI for DJF of the season year.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "outputs"
ONI_NOW = 2.46  # ASO 2026, latest value in noaa_oni_2012_2026.csv; DJF 2027 is not known yet


def guanacaste_points() -> tuple[pd.DataFrame, int]:
    df = pd.read_csv(DATA / "vigia_orbital_firms_costa_rica_2012_2025.csv", dtype={"acq_time": str})
    df["acq_date"] = pd.to_datetime(df.acq_date)
    prov = gpd.read_file(DATA / "costa_rica_provincias_geoboundaries.geojson")
    cant = gpd.read_file(DATA / "costa_rica_cantones_geoboundaries.geojson")
    gte = prov.loc[prov.shapeISO == "CR-G"].geometry.union_all()
    cant = cant.loc[cant.geometry.representative_point().within(gte), ["shapeName", "geometry"]]
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")
    g = gpd.sjoin(pts, cant, how="inner", predicate="within")
    return pd.DataFrame(g.drop(columns="geometry")), len(df)


def main() -> None:
    g, n_cr = guanacaste_points()
    print(f"Guanacaste share of CR detections (all sensors): {len(g)/n_cr:.1%} ({len(g):,}/{n_cr:,})")
    for src in ["viirs-snpp", "viirs-jpss1", "modis", None]:
        s = g if src is None else g[g.source == src]
        share = s.acq_date.dt.month.isin([2, 3, 4]).mean()
        print(f"Feb-Apr share, {src or 'all sensors'}: {share:.1%}")

    oni = pd.read_csv(DATA / "noaa_oni_2012_2026.csv")
    djf = oni[oni.season == "DJF"].set_index("year")["oni_anomaly"]

    g["season_cal"] = g.acq_date.dt.year
    g["season_novoct"] = g.acq_date.dt.year + (g.acq_date.dt.month >= 11)
    table = {}
    for src in ["viirs-snpp", "modis", "viirs-jpss1"]:
        for col in ["season_cal", "season_novoct"]:
            c = g[g.source == src].groupby(col).size()
            if col == "season_novoct":  # drop partial first/last seasons
                c = c.loc[2013:2025]
            if src == "viirs-jpss1":
                c = c.loc[2019:]  # NOAA-20 data start 2018 (partial)
            table[(src, col)] = c

    main_series = table[("viirs-snpp", "season_cal")]
    d = pd.DataFrame({"gte_viirs_snpp": main_series, "oni_djf": djf}).dropna()
    d["rank"] = d.gte_viirs_snpp.rank(ascending=False).astype(int)
    d = d.sort_values("rank")
    print("\nGuanacaste VIIRS S-NPP detections per season (calendar year):")
    print(d.to_string())
    d.to_csv(OUT / "gte_season_enso.csv")

    print("\nRobustness: top-3 seasons and correlation with DJF ONI")
    for (src, col), c in table.items():
        x = pd.concat([c.rename("n"), djf], axis=1, join="inner")
        r, p = stats.pearsonr(x.n, x.oni_anomaly)
        top = c.sort_values(ascending=False).head(3)
        print(f"  {src:12s} {col:14s} n={len(x):2d} r={r:+.2f} (p={p:.2f}) top3={dict(top)}")

    r, p = stats.pearsonr(d.gte_viirs_snpp, d.oni_djf)
    print(f"\nMain: r={r:.2f}, r^2={r*r:.2f}, p={p:.2f}, n={len(d)}")
    med = d.gte_viirs_snpp.median()
    print(f"Median season: {med:.0f}")
    strong = d[d.oni_djf >= 1.5]
    print("Strong El Nino seasons (DJF ONI >= 1.5):")
    print(strong.assign(above_median=strong.gte_viirs_snpp > med).to_string())
    print(f"Range of all seasons: {d.gte_viirs_snpp.min():.0f}-{d.gte_viirs_snpp.max():.0f}")

    # OLS prediction interval at the current ONI (an extrapolation-ish proxy:
    # max observed DJF ONI is 2.50).
    x, y = d.oni_djf.to_numpy(), d.gte_viirs_snpp.to_numpy()
    n = len(x)
    b1, b0 = np.polyfit(x, y, 1)
    resid = y - (b0 + b1 * x)
    s = np.sqrt((resid ** 2).sum() / (n - 2))
    se_pred = s * np.sqrt(1 + 1 / n + (ONI_NOW - x.mean()) ** 2 / ((x - x.mean()) ** 2).sum())
    yhat = b0 + b1 * ONI_NOW
    for level in (0.8, 0.95):
        t = stats.t.ppf(0.5 + level / 2, n - 2)
        print(f"OLS at ONI={ONI_NOW}: {yhat:.0f}, {int(level*100)}% PI {yhat - t*se_pred:.0f}-{yhat + t*se_pred:.0f}")


if __name__ == "__main__":
    main()
