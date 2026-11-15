"""Download HDX-listed layers and clip them to Guanacaste for the offline app.

Raw downloads go to data/raw_hdx/ (git-ignored; re-downloaded if missing).
Outputs (WGS84) in data/:
  guanacaste_poblacion_kontur_h3_400m.geojson  Kontur population, H3 400 m hexagons
  costa_rica_poblacion_distritos_unfpa_2021.csv UNFPA population by district (national copy)
  guanacaste_caminos_hotosm.geojson            OSM roads usable by vehicles (incl. tracks)
  guanacaste_poblados_hotosm.geojson           OSM populated places
  guanacaste_salud_hotosm.geojson              OSM health facilities (as points)
  guanacaste_bomberos_hotosm.geojson           OSM fire stations (amenity=fire_station)
Clip area = Guanacaste province (geoBoundaries) buffered by 2 km.
"""
import gzip
import shutil
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw_hdx"
HOT = "https://production-raw-data-api.s3.amazonaws.com/ISO3/CRI"
SOURCES = {
    "kontur_population_CR_20231101.gpkg.gz": "https://geodata-eu-central-1-kontur-public.s3.amazonaws.com/kontur_datasets/kontur_population_CR_20231101.gpkg.gz",
    "cri_admpop_adm3_unfpa2021.csv": "https://data.humdata.org/dataset/2ed8eb18-6df3-4e31-b907-4902334d0bbf/resource/bcaf2420-b334-44c5-86cf-fbba4669184d/download/cri_admpop_adm3_unfpa2021.csv",
    "hotosm_cri_roads_osm_gpkg.zip": f"{HOT}/roads/hotosm_cri_roads_osm_gpkg.zip",
    "hotosm_cri_populated_places_osm_geojson.zip": f"{HOT}/populated_places/hotosm_cri_populated_places_osm_geojson.zip",
    "hotosm_cri_health_facilities_osm_geojson.zip": f"{HOT}/health_facilities/hotosm_cri_health_facilities_osm_geojson.zip",
    "hotosm_cri_points_of_interest_osm_geojson.zip": f"{HOT}/points_of_interest/hotosm_cri_points_of_interest_osm_geojson.zip",
}
VEHICLE_ROADS = {
    "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "unclassified", "residential", "living_street",
    "service", "track", "motorway", "motorway_link",
}


def fetch() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        dst = RAW / name
        if not dst.exists():
            print("downloading", name)
            with urllib.request.urlopen(url, timeout=600) as r, open(dst, "wb") as f:
                shutil.copyfileobj(r, f)


def from_zip(zip_name: str, member: str) -> str:
    return f"zip://{RAW / zip_name}!{member}"


def clip_area() -> gpd.GeoSeries:
    prov = gpd.read_file(DATA / "costa_rica_provincias_geoboundaries.geojson").to_crs(5367)
    gte = prov.loc[prov.shapeISO == "CR-G"].geometry.union_all().buffer(2000)
    return gpd.GeoSeries([gte], crs=5367).to_crs(4326)


def clip(gdf: gpd.GeoDataFrame, area: gpd.GeoSeries) -> gpd.GeoDataFrame:
    gdf = gdf.to_crs(4326)
    return gdf[gdf.intersects(area.iloc[0])].copy()


def save(gdf: gpd.GeoDataFrame, name: str) -> None:
    out = DATA / name
    gdf.to_file(out, driver="GeoJSON", COORDINATE_PRECISION=5)
    print(f"{name}: {len(gdf):,} features, {out.stat().st_size/1e6:.2f} MB")


def main() -> None:
    fetch()
    area = clip_area()

    kontur_gpkg = RAW / "kontur_population_CR_20231101.gpkg"
    if not kontur_gpkg.exists():
        with gzip.open(RAW / "kontur_population_CR_20231101.gpkg.gz") as src, open(kontur_gpkg, "wb") as dst:
            shutil.copyfileobj(src, dst)
    pop = clip(gpd.read_file(kontur_gpkg), area)[["h3", "population", "geometry"]]
    pop["population"] = pop.population.round().astype(int)
    save(pop, "guanacaste_poblacion_kontur_h3_400m.geojson")

    shutil.copyfile(RAW / "cri_admpop_adm3_unfpa2021.csv", DATA / "costa_rica_poblacion_distritos_unfpa_2021.csv")
    unfpa = pd.read_csv(DATA / "costa_rica_poblacion_distritos_unfpa_2021.csv")
    print("UNFPA districts:", len(unfpa), "| Guanacaste population 2021:",
          int(unfpa.loc[unfpa.ADM1_ES == "Guanacaste", "T_TL"].sum()))

    roads = gpd.read_file(from_zip("hotosm_cri_roads_osm_gpkg.zip", "roads.gpkg"),
                          columns=["id", "name", "highway", "surface"])
    roads = roads[roads.highway.isin(VEHICLE_ROADS) & roads.geom_type.isin(["LineString", "MultiLineString"])]
    save(clip(roads, area), "guanacaste_caminos_hotosm.geojson")

    places = gpd.read_file(from_zip("hotosm_cri_populated_places_osm_geojson.zip", "populated_places.geojson"),
                           columns=["id", "name", "place", "population"])
    places["geometry"] = places.geometry.representative_point()
    save(clip(places, area), "guanacaste_poblados_hotosm.geojson")

    health = gpd.read_file(from_zip("hotosm_cri_health_facilities_osm_geojson.zip", "health_facilities.geojson"),
                           columns=["id", "name", "amenity", "healthcare", "operator_type"])
    health["geometry"] = health.geometry.representative_point()
    save(clip(health, area), "guanacaste_salud_hotosm.geojson")

    poi = gpd.read_file(from_zip("hotosm_cri_points_of_interest_osm_geojson.zip", "points_of_interest.geojson"),
                        columns=["id", "name", "amenity", "addr_city"])
    fire = poi[poi.amenity == "fire_station"].copy()
    fire["geometry"] = fire.geometry.representative_point()
    print("fire stations in Costa Rica (OSM):", len(fire))
    save(clip(fire, area), "guanacaste_bomberos_hotosm.geojson")


if __name__ == "__main__":
    main()
