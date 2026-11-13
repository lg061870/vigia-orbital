"""Precompute MODIS NDVI and NBR for Guanacaste, 2012-2025 (data prep).

Source: MOD13Q1 / MYD13Q1 v061 (Terra / Aqua 16-day vegetation indices, 250 m),
read as cloud-optimized GeoTIFFs from Microsoft Planetary Computer (no login).
Terra and Aqua composites are offset by 8 days, so together they give one
composite every 8 days. Tiles h09v07 + h09v08 cover Guanacaste.

Per composite: NDVI (the product's own layer) and NBR = (NIR - MIR) / (NIR + MIR),
where MIR is MODIS band 7 (2.1 um, SWIR2). Pixels whose pixel_reliability is not
0 (good) or 1 (marginal) are masked. Everything is warped to a common grid in
EPSG:4326 over the WorldCover bbox (lon -86.0..-84.7, lat 9.6..11.25), 0.0025 deg.

Outputs:
  data/raw_modis/<date>_<sensor>.tif     2-band int16 stack (NDVI, NBR x 10000), git-ignored
  data/modis_ndvi_nbr_canton_8day_2012_2025.csv   mean / valid share per canton and composite
  data/modis_season/season_<Y>.tif       per season year Y (see seasonal())
"""
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.vrt import WarpedVRT

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw_modis"
SEASON = DATA / "modis_season"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token/modiseuwest/modis-061-cogs"
W, S, E, N = -86.0, 9.6, -84.7, 11.25
RES = 0.0025
WIDTH, HEIGHT = round((E - W) / RES), round((N - S) / RES)
TRANSFORM = from_bounds(W, S, E, N, WIDTH, HEIGHT)
NODATA = -32768
ASSETS = {"ndvi": "250m_16_days_NDVI", "nir": "250m_16_days_NIR_reflectance",
          "mir": "250m_16_days_MIR_reflectance", "rel": "250m_16_days_pixel_reliability"}


def http_json(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(url)


class Token:
    def __init__(self):
        self.value, self.t = None, 0

    def get(self):
        if time.time() - self.t > 1800:
            self.value, self.t = http_json(SAS)["token"], time.time()
        return self.value


def search_items(year):
    body = {"collections": ["modis-13Q1-061"], "bbox": [W, S, E, N],
            "datetime": f"{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z", "limit": 200}
    feats = http_json(STAC, body)["features"]
    return [f for f in feats if f["id"].split(".")[2] in ("h09v07", "h09v08")]


def read_band(href, token, resampling):
    with rasterio.open(f"/vsicurl/{href}?{token}") as src:
        with WarpedVRT(src, crs="EPSG:4326", transform=TRANSFORM, width=WIDTH, height=HEIGHT,
                       resampling=resampling, src_nodata=src.nodata, nodata=src.nodata) as vrt:
            return vrt.read(1), vrt.nodata


def process(key, tiles, token):
    out = RAW / f"{key}.tif"
    if out.exists():
        return key
    ndvi = np.full((HEIGHT, WIDTH), NODATA, np.int16)
    nbr = np.full((HEIGHT, WIDTH), NODATA, np.int16)
    for f in tiles:
        a = {k: f["assets"][v]["href"] for k, v in ASSETS.items()}
        tok = token.get()
        rel, rel_nd = read_band(a["rel"], tok, Resampling.nearest)
        ok = np.isin(rel, (0, 1))
        nd, _ = read_band(a["ndvi"], tok, Resampling.nearest)
        nir, _ = read_band(a["nir"], tok, Resampling.nearest)
        mir, _ = read_band(a["mir"], tok, Resampling.nearest)
        nir_f, mir_f = nir.astype(np.float32), mir.astype(np.float32)
        den = nir_f + mir_f
        valid = ok & (nir > 0) & (mir > 0) & (den > 0)
        nbr_t = np.where(valid, np.round((nir_f - mir_f) / np.where(den == 0, 1, den) * 10000), NODATA).astype(np.int16)
        fill = valid & (ndvi == NODATA)
        ndvi[fill] = nd[fill]
        nbr[fill] = nbr_t[fill]
    profile = dict(driver="GTiff", height=HEIGHT, width=WIDTH, count=2, dtype="int16", crs="EPSG:4326",
                   transform=TRANSFORM, nodata=NODATA, compress="deflate", predictor=2, tiled=True)
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(ndvi, 1)
        dst.write(nbr, 2)
        dst.set_band_description(1, "NDVI x10000")
        dst.set_band_description(2, "NBR x10000")
    return key


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    token = Token()
    groups = {}
    for year in range(2011, 2026):  # 2011 for the Dec 2011 pre-season of 2012
        for f in search_items(year):
            sensor = f["id"].split(".")[0][:3]  # MOD or MYD
            date = f["properties"]["start_datetime"][:10]
            groups.setdefault(f"{date}_{sensor}", []).append(f)
    keys = sorted(k for k in groups if k >= "2011-11-01")
    print(f"{len(keys)} composites to process", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for _ in ex.map(lambda k: process(k, groups[k], token), keys):
            done += 1
            if done % 25 == 0:
                print(f"{done}/{len(keys)}", flush=True)


def canton_series():
    prov = gpd.read_file(DATA / "costa_rica_provincias_geoboundaries.geojson")
    cant = gpd.read_file(DATA / "costa_rica_cantones_geoboundaries.geojson")
    gte = prov.loc[prov.shapeISO == "CR-G"].geometry.union_all()
    cant = cant.loc[cant.geometry.representative_point().within(gte)].reset_index(drop=True)
    zones = rasterize(((g, i + 1) for i, g in enumerate(cant.geometry)), out_shape=(HEIGHT, WIDTH),
                      transform=TRANSFORM, fill=0, dtype="int16")
    rows = []
    for f in sorted(RAW.glob("*.tif")):
        date, sensor = f.stem.split("_")
        with rasterio.open(f) as src:
            ndvi, nbr = src.read(1), src.read(2)
        for i, name in enumerate(cant.shapeName):
            z = zones == i + 1
            v = z & (ndvi != NODATA)
            rows.append({"date": date, "sensor": sensor, "canton": name,
                         "ndvi_mean": round(float(ndvi[v].mean()) / 1e4, 4) if v.any() else None,
                         "nbr_mean": round(float(nbr[v].mean()) / 1e4, 4) if v.any() else None,
                         "valid_share": round(float(v.sum() / z.sum()), 3)})
    out = DATA / "modis_ndvi_nbr_canton_8day_2012_2025.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(out.name, len(rows), "rows")


def median_stack(files, band):
    arrs = []
    for f in files:
        with rasterio.open(f) as src:
            a = src.read(band).astype(np.float32)
        a[a == NODATA] = np.nan
        arrs.append(a)
    return np.nanmedian(np.stack(arrs), axis=0) if arrs else np.full((HEIGHT, WIDTH), np.nan, np.float32)


def seasonal():
    """Per season year Y (dry season peaks Feb-Apr):
    pre  = median of composites starting 1 Dec (Y-1) .. 31 Jan Y
    peak = median of composites starting 1 Mar .. 31 Mar Y
    post = median of composites starting 16 Apr .. 31 May Y
    Bands: NDVI_pre, NBR_pre, NDVI_peak, NBR_post, dNBR (= NBR_pre - NBR_post),
    dNBR_anom (= dNBR minus the 2012-2025 per-pixel median dNBR, i.e. the part
    not explained by normal dry-season leaf loss). All x10000, int16.
    """
    SEASON.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW.glob("*.tif"))
    by_date = [(pd.Timestamp(f.stem.split("_")[0]), f) for f in files]

    def pick(a, b):
        return [f for d, f in by_date if pd.Timestamp(a) <= d <= pd.Timestamp(b)]

    per_year = {}
    for y in range(2012, 2026):
        pre = pick(f"{y-1}-12-01", f"{y}-01-31")
        peak = pick(f"{y}-03-01", f"{y}-03-31")
        post = pick(f"{y}-04-16", f"{y}-05-31")
        nbr_pre, nbr_post = median_stack(pre, 2), median_stack(post, 2)
        per_year[y] = dict(ndvi_pre=median_stack(pre, 1), nbr_pre=nbr_pre,
                           ndvi_peak=median_stack(peak, 1), nbr_post=nbr_post, dnbr=nbr_pre - nbr_post)
    dnbr_median = np.nanmedian(np.stack([v["dnbr"] for v in per_year.values()]), axis=0)
    names = ["NDVI_pre", "NBR_pre", "NDVI_peak", "NBR_post", "dNBR", "dNBR_anom"]
    for y, v in per_year.items():
        bands = [v["ndvi_pre"], v["nbr_pre"], v["ndvi_peak"], v["nbr_post"], v["dnbr"], v["dnbr"] - dnbr_median]
        profile = dict(driver="GTiff", height=HEIGHT, width=WIDTH, count=len(bands), dtype="int16",
                       crs="EPSG:4326", transform=TRANSFORM, nodata=NODATA, compress="deflate", predictor=2, tiled=True)
        with rasterio.open(SEASON / f"season_{y}.tif", "w", **profile) as dst:
            for i, (b, n) in enumerate(zip(bands, names), start=1):
                dst.write(np.where(np.isnan(b), NODATA, np.round(b)).astype(np.int16), i)
                dst.set_band_description(i, f"{n} x10000")
    print("season rasters:", len(per_year))


if __name__ == "__main__":
    steps = sys.argv[1:] or ["download", "canton", "season"]
    if "download" in steps:
        download()
    if "canton" in steps:
        canton_series()
    if "season" in steps:
        seasonal()
