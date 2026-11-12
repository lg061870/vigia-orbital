"""Sanity check of the Vigía Orbital data kit.

Counts FIRMS detections per year and source, assigns each detection to a
Guanacaste canton (point-in-polygon with geoBoundaries ADM2), and reports the
VIIRS/MODIS ratio by year. Writes CSV summaries to outputs/.
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)


def load_hotspots() -> gpd.GeoDataFrame:
    df = pd.read_csv(DATA / "vigia_orbital_firms_costa_rica_2012_2025.csv",
                     dtype={"acq_time": str, "confidence": str})
    df["acq_date"] = pd.to_datetime(df["acq_date"])
    df["year"] = df["acq_date"].dt.year
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")


def guanacaste_cantons() -> gpd.GeoDataFrame:
    prov = gpd.read_file(DATA / "costa_rica_provincias_geoboundaries.geojson")
    cant = gpd.read_file(DATA / "costa_rica_cantones_geoboundaries.geojson")
    gte = prov.loc[prov.shapeISO == "CR-G"].geometry.union_all()
    # A canton belongs to Guanacaste if its interior point lies in the province polygon.
    inside = cant.geometry.representative_point().within(gte)
    return cant.loc[inside, ["shapeName", "geometry"]].rename(columns={"shapeName": "canton"})


def main() -> None:
    pts = load_hotspots()
    print(f"Total detections: {len(pts):,}")
    print(f"Date range: {pts.acq_date.min().date()} .. {pts.acq_date.max().date()}")

    by_year = pts.pivot_table(index="year", columns="source", values="latitude",
                              aggfunc="size", fill_value=0)
    by_year["ratio_snpp_modis"] = (by_year["viirs-snpp"] / by_year["modis"]).round(2)
    by_year["ratio_noaa20_modis"] = (by_year["viirs-jpss1"] / by_year["modis"]).where(by_year["viirs-jpss1"] > 0).round(2)
    print("\nCosta Rica, detections per year and source:\n", by_year)
    by_year.to_csv(OUT / "cr_detections_by_year_source.csv")

    cantons = guanacaste_cantons()
    print(f"\nGuanacaste cantons found: {len(cantons)} -> {sorted(cantons.canton)}")
    g = gpd.sjoin(pts, cantons, how="inner", predicate="within")
    print(f"Detections inside Guanacaste: {len(g):,} ({len(g)/len(pts):.1%} of CR)")

    gy = g.pivot_table(index="year", columns="source", values="latitude", aggfunc="size", fill_value=0)
    gy["ratio_snpp_modis"] = (gy["viirs-snpp"] / gy["modis"]).round(2)
    print("\nGuanacaste, detections per year and source:\n", gy)
    gy.to_csv(OUT / "gte_detections_by_year_source.csv")

    gc = g.pivot_table(index="canton", columns="source", values="latitude", aggfunc="size", fill_value=0)
    gc["ratio_snpp_modis"] = (gc["viirs-snpp"] / gc["modis"]).round(2)
    gc = gc.sort_values("viirs-snpp", ascending=False)
    print("\nGuanacaste, detections per canton 2012-2025:\n", gc)
    gc.to_csv(OUT / "gte_detections_by_canton_source.csv")

    gcy = g[g.source == "viirs-snpp"].pivot_table(index="canton", columns="year", values="latitude",
                                                   aggfunc="size", fill_value=0)
    print("\nGuanacaste, VIIRS S-NPP detections per canton and year:\n", gcy.to_string())
    gcy.to_csv(OUT / "gte_snpp_by_canton_year.csv")

    months = g[g.source == "viirs-snpp"].acq_date.dt.month.value_counts().sort_index()
    print("\nGuanacaste VIIRS S-NPP by month (all years):\n", months.to_string())


if __name__ == "__main__":
    main()
