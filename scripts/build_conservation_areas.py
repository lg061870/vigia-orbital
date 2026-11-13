"""Build the conservation-area layer and the canton -> conservation area table.

Input: data/raw/sirefor_limites_areas_conservacion_2021_CRTM05.zip, i.e. the
SIREFOR WFS layer SIREFORV2:aprovechamiento_areas_conservacion_numpermisos_2021
(one polygon per SINAC conservation area, EPSG:5367). Only code/name/abbreviation
are kept; the harvest-permit columns are dropped. Geometry is simplified to 20 m
(well below the 375 m VIIRS pixel) so the layer is light enough for Leaflet.
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw" / "sirefor_limites_areas_conservacion_2021_CRTM05.zip"
OUT_GEOJSON = DATA / "costa_rica_areas_conservacion_sirefor_2021.geojson"
OUT_TABLE = DATA / "guanacaste_canton_area_conservacion.csv"
TOLERANCE_M = 20


def main() -> None:
    ac = gpd.read_file(f"zip://{RAW}")
    assert ac.crs.to_epsg() == 5367
    ac = ac[["codigo_ac", "nombre_ac", "siglas_ac", "geometry"]].rename(
        columns={"codigo_ac": "ac_code", "nombre_ac": "ac_name", "siglas_ac": "ac_abbr"}
    ).sort_values("ac_code")
    ac["geometry"] = ac.geometry.simplify(TOLERANCE_M, preserve_topology=True)
    assert ac.is_valid.all()
    ac.to_crs(4326).to_file(OUT_GEOJSON, driver="GeoJSON", COORDINATE_PRECISION=5)

    prov = gpd.read_file(DATA / "costa_rica_provincias_geoboundaries.geojson").to_crs(5367)
    cant = gpd.read_file(DATA / "costa_rica_cantones_geoboundaries.geojson").to_crs(5367)
    gte = prov.loc[prov.shapeISO == "CR-G"].geometry.union_all()
    cant = cant.loc[cant.geometry.representative_point().within(gte), ["shapeName", "geometry"]]
    cant = cant.rename(columns={"shapeName": "canton"})
    cant["canton_km2"] = cant.area / 1e6

    ov = gpd.overlay(cant, ac, how="intersection", keep_geom_type=True)
    ov["share"] = ov.area / 1e6 / ov.canton_km2
    best = ov.sort_values("share", ascending=False).drop_duplicates("canton")
    table = best[["canton", "ac_code", "ac_abbr", "ac_name", "share"]].sort_values(["ac_code", "canton"])
    table["share"] = table.share.round(3)
    assert len(table) == 11 and (table.share >= 0.95).all(), table
    table.to_csv(OUT_TABLE, index=False)
    print(table.to_string(index=False))
    print(f"{OUT_GEOJSON.name}: {OUT_GEOJSON.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
