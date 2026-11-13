"""Build data/vigia_orbital.duckdb from the files in data/ (data prep only).

Tables (geometry stored as WKB blobs, EPSG:4326; distances computed in CRTM05):
  canton             83 cantons: canton_id (UNFPA ADM2 pcode, or GB-<name> for
                     cantons UNFPA 2021 lacks), names, province, ac_code, area, pop_2021
  conservation_area  10 SINAC areas (SIREFOR)
  protected_area     132 OSM protected areas
  detection          129,973 FIRMS points + canton_id, h3 (res 8), in_protected_area,
                     dist_protected_area_km
  cell               Guanacaste H3 res-8 hexagons (Kontur grid): population, canton_id,
                     WorldCover class at centroid, distances to protected area / road /
                     fire station / populated place
  weather_day        NASA POWER daily per canton seat (+ 2 reference points)
  vi_canton_8day     MODIS NDVI / NBR per canton and 8-day composite
  oni                ONI by 3-month season
  population_district UNFPA 2021 by district (totals)
  facility           fire stations, health facilities, populated places (OSM)
  raster_catalog     paths and bands of the GeoTIFFs kept as files
Views:
  canton_day         canton x day 2012-2025: weather + latest MODIS composite (as-of
                     join) + ONI of the season containing the month. No fire counts
                     yet: the harmonized count is built at the event.
"""
import unicodedata
from pathlib import Path

import duckdb
import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = DATA / "vigia_orbital.duckdb"
CR = 5367
# geoBoundaries spelling -> UNFPA spelling (old names / typos); others match after accent folding
ALIASES = {"vazquez de coronado": "vasquez de coronado", "leon cortes castro": "leon cortes",
           "sarchi": "valverde vega", "palmeras": "palmares", "quepos": "aguirre"}
ONI_MONTH = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
             "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}  # centre month


def fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def wkb(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    df = pd.DataFrame(gdf.drop(columns="geometry"))
    df["geom_wkb"] = gdf.geometry.to_wkb()
    return df


def km_to_nearest(points: gpd.GeoDataFrame, targets: gpd.GeoDataFrame) -> np.ndarray:
    p, t = points.to_crs(CR), targets.to_crs(CR)[["geometry"]]
    j = gpd.sjoin_nearest(p[["geometry"]], t, distance_col="d")
    return (j.groupby(level=0)["d"].min().reindex(p.index) / 1000).round(3).to_numpy()


def build_canton():
    g = gpd.read_file(DATA / "costa_rica_cantones_geoboundaries.geojson")[["shapeName", "geometry"]]
    prov = gpd.read_file(DATA / "costa_rica_provincias_geoboundaries.geojson")[["shapeName", "geometry"]]
    u = pd.read_csv(DATA / "costa_rica_poblacion_distritos_unfpa_2021.csv")
    u2 = u.groupby(["ADM2_PCODE"]).agg(name_es=("ADM2_ES", "first"), pop_2021=("T_TL", "sum")).reset_index()
    u2["key"] = u2.name_es.map(fold)
    u2 = u2.drop_duplicates("key")
    g["key"] = g.shapeName.map(fold).replace(ALIASES)
    c = g.merge(u2, on="key", how="left")
    c["canton_id"] = c.ADM2_PCODE.fillna("GB-" + c.shapeName.str.replace(" ", "_"))
    c["name_es"] = c.name_es.fillna(c.shapeName)
    pts = gpd.GeoDataFrame(geometry=c.geometry.representative_point(), crs=c.crs)
    c["province"] = gpd.sjoin(pts, prov, predicate="within")["shapeName"].str.replace("Provincia ", "")
    ac = gpd.read_file(DATA / "costa_rica_areas_conservacion_sirefor_2021.geojson")
    c["ac_code"] = gpd.sjoin(pts, ac[["ac_code", "geometry"]], how="left", predicate="within")["ac_code"]
    c["area_km2"] = (c.to_crs(CR).area / 1e6).round(1)
    c = c.rename(columns={"shapeName": "name"})
    return c[["canton_id", "name", "name_es", "province", "ac_code", "area_km2", "pop_2021", "geometry"]]


def main() -> None:
    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))

    canton = build_canton()
    canton_df = wkb(canton)
    con.execute("CREATE TABLE canton AS SELECT * FROM canton_df")
    name_to_id = dict(zip(canton.name, canton.canton_id))

    ac = gpd.read_file(DATA / "costa_rica_areas_conservacion_sirefor_2021.geojson")
    ac_df = wkb(ac)
    con.execute("CREATE TABLE conservation_area AS SELECT * FROM ac_df")

    pa = gpd.read_file(DATA / "costa_rica_areas_protegidas_osm.geojson")
    pa = pa[["osm_id", "name", "boundary", "leisure", "protect_class", "protection_title", "geometry"]]
    pa_df = wkb(pa)
    con.execute("CREATE TABLE protected_area AS SELECT * FROM pa_df")

    # detections
    d = pd.read_csv(DATA / "vigia_orbital_firms_costa_rica_2012_2025.csv", dtype={"acq_time": str, "confidence": str})
    d.insert(0, "detection_id", np.arange(1, len(d) + 1))
    d["acq_datetime_utc"] = pd.to_datetime(d.acq_date + " " + d.acq_time.str.zfill(4), format="%Y-%m-%d %H%M")
    pts = gpd.GeoDataFrame(d[["detection_id"]], geometry=gpd.points_from_xy(d.longitude, d.latitude), crs=4326)
    j = gpd.sjoin(pts, canton[["canton_id", "geometry"]], how="left", predicate="within")
    d["canton_id"] = j.groupby(level=0)["canton_id"].first().to_numpy()
    d["h3"] = [h3.latlng_to_cell(la, lo, 8) for la, lo in zip(d.latitude, d.longitude)]
    d["in_protected_area"] = gpd.sjoin(pts, pa[["geometry"]], how="left", predicate="within") \
        .groupby(level=0)["index_right"].count().gt(0).to_numpy()
    d["dist_protected_area_km"] = km_to_nearest(pts, pa)
    det_df = d
    con.execute("CREATE TABLE detection AS SELECT * FROM det_df")

    # H3 cells (Guanacaste, Kontur grid)
    cell = gpd.read_file(DATA / "guanacaste_poblacion_kontur_h3_400m.geojson")
    cent = gpd.GeoDataFrame(cell[["h3"]], geometry=[gpd.points_from_xy([h3.cell_to_latlng(x)[1]], [h3.cell_to_latlng(x)[0]])[0] for x in cell.h3], crs=4326)
    cell["canton_id"] = gpd.sjoin(cent, canton[["canton_id", "geometry"]], how="left", predicate="within") \
        .groupby(level=0)["canton_id"].first().to_numpy()
    with rasterio.open(DATA / "esa_worldcover_2021_guanacaste_~35m.tif") as src:
        cell["landcover_centroid"] = [v[0] for v in src.sample(zip(cent.geometry.x, cent.geometry.y))]
    roads = gpd.read_file(DATA / "guanacaste_caminos_hotosm.geojson")
    fire = gpd.read_file(DATA / "guanacaste_bomberos_hotosm.geojson")
    places = gpd.read_file(DATA / "guanacaste_poblados_hotosm.geojson")
    cell["dist_protected_area_km"] = km_to_nearest(cent, pa)
    cell["dist_road_km"] = km_to_nearest(cent, roads)
    cell["dist_fire_station_km"] = km_to_nearest(cent, fire)
    cell["dist_populated_place_km"] = km_to_nearest(cent, places)
    cell_df = wkb(cell)
    con.execute("CREATE TABLE cell AS SELECT * FROM cell_df")

    fac = pd.concat([
        wkb(fire[["id", "name", "geometry"]]).assign(kind="fire_station", subtype=None),
        wkb(gpd.read_file(DATA / "guanacaste_salud_hotosm.geojson")[["id", "name", "amenity", "geometry"]]
            .rename(columns={"amenity": "subtype"})).assign(kind="health"),
        wkb(places[["id", "name", "place", "geometry"]].rename(columns={"place": "subtype"})).assign(kind="populated_place"),
    ], ignore_index=True)
    con.execute("CREATE TABLE facility AS SELECT * FROM fac")

    w = pd.read_csv(DATA / "nasa_power_guanacaste_daily_2012_2025.csv")
    w["date"] = pd.to_datetime(w.YEAR.astype(str), format="%Y") + pd.to_timedelta(w.DOY - 1, unit="D")
    w["canton_id"] = w.canton.map(name_to_id)  # reference points (Puntarenas, San Jose ref) keep NULL
    w_df = w
    con.execute("CREATE TABLE weather_day AS SELECT * FROM w_df")

    vi = pd.read_csv(DATA / "modis_ndvi_nbr_canton_8day_2012_2025.csv", parse_dates=["date"])
    vi["canton_id"] = vi.canton.map(name_to_id)
    vi_df = vi
    con.execute("CREATE TABLE vi_canton_8day AS SELECT * FROM vi_df")

    oni = pd.read_csv(DATA / "noaa_oni_2012_2026.csv")
    oni["center_month"] = oni.season.map(ONI_MONTH)
    oni_df = oni
    con.execute("CREATE TABLE oni AS SELECT * FROM oni_df")

    pop = pd.read_csv(DATA / "costa_rica_poblacion_distritos_unfpa_2021.csv")
    pop_df = pop[["ADM1_ES", "ADM1_PCODE", "ADM2_ES", "ADM2_PCODE", "ADM3_ES", "ADM3_PCODE", "F_TL", "M_TL", "T_TL"]]
    con.execute("CREATE TABLE population_district AS SELECT * FROM pop_df")

    cat = [{"path": f"data/modis_season/season_{y}.tif", "kind": "modis_season", "season_year": y,
            "bands": "NDVI_pre,NBR_pre,NDVI_peak,NBR_post,dNBR,dNBR_anom", "scale": 1e-4}
           for y in range(2012, 2026)]
    cat.append({"path": "data/esa_worldcover_2021_guanacaste_~35m.tif", "kind": "landcover", "season_year": None,
                "bands": "class", "scale": 1})
    cat_df = pd.DataFrame(cat)
    con.execute("CREATE TABLE raster_catalog AS SELECT * FROM cat_df")

    con.execute("""
        CREATE VIEW canton_day AS
        SELECT w.canton_id, w.canton, w.date,
               w.T2M, w.T2M_MAX, w.T2M_MIN, w.PRECTOTCORR, w.RH2M, w.WS2M, w.GWETTOP,
               v.date AS vi_date, v.ndvi_mean, v.nbr_mean, v.valid_share AS vi_valid_share,
               o.oni_anomaly
        FROM weather_day w
        ASOF LEFT JOIN (SELECT * FROM vi_canton_8day WHERE valid_share >= 0.3) v
          ON w.canton_id = v.canton_id AND w.date >= v.date
        LEFT JOIN oni o
          ON o.year = year(w.date) AND o.center_month = month(w.date)
        WHERE w.canton_id IS NOT NULL
    """)

    for t in ["canton", "conservation_area", "protected_area", "detection", "cell", "facility",
              "weather_day", "vi_canton_8day", "oni", "population_district", "raster_catalog", "canton_day"]:
        print(f"{t:20s} {con.execute(f'SELECT count(*) FROM {t}').fetchone()[0]:>8,}")
    con.close()
    print(f"{DB.name}: {DB.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
