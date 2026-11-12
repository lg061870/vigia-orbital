"""Verify that NASA POWER points join to the right Guanacaste canton.

Checks: (1) every Guanacaste canton in geoBoundaries has a POWER series with the
same name; (2) each POWER point (canton seat) falls inside the polygon of the
canton it is named after; (3) the series are complete (one row per day).
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
REFERENCE_POINTS = {"Puntarenas", "San Jose ref"}  # outside Guanacaste by design


def main() -> None:
    power = pd.read_csv(DATA / "nasa_power_guanacaste_daily_2012_2025.csv")
    prov = gpd.read_file(DATA / "costa_rica_provincias_geoboundaries.geojson")
    cant = gpd.read_file(DATA / "costa_rica_cantones_geoboundaries.geojson")
    gte = prov.loc[prov.shapeISO == "CR-G"].geometry.union_all()
    gte_cant = cant.loc[cant.geometry.representative_point().within(gte), ["shapeName", "geometry"]]

    names_power = set(power.canton.unique())
    names_gte = set(gte_cant.shapeName)
    print("Guanacaste cantons without POWER series:", sorted(names_gte - names_power) or "none")
    print("POWER series not in Guanacaste:", sorted(names_power - names_gte))
    assert names_gte <= names_power
    assert names_power - names_gte == REFERENCE_POINTS

    pts = power.groupby("canton", as_index=False)[["lat", "lon"]].first()
    pts = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts.lon, pts.lat), crs="EPSG:4326")
    joined = gpd.sjoin(pts, cant[["shapeName", "geometry"]], how="left", predicate="within")
    joined["match"] = joined.canton == joined.shapeName
    print(joined[["canton", "lat", "lon", "shapeName", "match"]].to_string(index=False))
    assert joined.loc[~joined.canton.isin(REFERENCE_POINTS), "match"].all()

    days = power.groupby("canton").size()
    expected = (pd.Timestamp("2025-12-31") - pd.Timestamp("2012-01-01")).days + 1
    print(f"Rows per series: {days.unique().tolist()} (expected {expected})")
    assert (days == expected).all()
    print("OK: POWER <-> geoBoundaries join verified")


if __name__ == "__main__":
    main()
