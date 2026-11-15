"""Export every table and view of data/vigia_orbital.duckdb to data/csv/<name>.csv.

Geometry blobs are not exported; tables with geometry get centroid_lon / centroid_lat
instead (full shapes are in the GeoJSON files in data/). Run after scripts/build_db.py.
"""
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "vigia_orbital.duckdb"
OUT = ROOT / "data" / "csv"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)
    names = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables ORDER BY table_name").fetchall()]
    for t in names:
        df = con.execute(f"SELECT * FROM {t}").df()
        if "geom_wkb" in df:
            g = gpd.GeoSeries.from_wkb(df.pop("geom_wkb").apply(bytes), crs=4326)
            c = g.to_crs(5367).centroid.to_crs(4326)
            df["centroid_lon"], df["centroid_lat"] = c.x.round(6), c.y.round(6)
        df.to_csv(OUT / f"{t}.csv", index=False)
        print(f"{t:22s} {len(df):>8,} rows  {(OUT / f'{t}.csv').stat().st_size/1e6:6.1f} MB")
    con.close()


if __name__ == "__main__":
    main()
