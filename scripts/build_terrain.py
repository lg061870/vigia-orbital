"""Terrain for Guanacaste from NASADEM (NASA, 1 arc-second ~30 m), via Planetary Computer.

Mosaics the NASADEM tiles over the WorldCover bbox (lon -86.0..-84.7, lat 9.6..11.25),
resamples to 3 arc-seconds (~90 m, bilinear), and computes:
  slope_deg   = degrees(arctan(sqrt(dz/dx^2 + dz/dy^2)))   (central differences;
                dx, dy in metres from the pixel size at each latitude)
  aspect_deg  = direction the slope faces, 0 = north, 90 = east (clockwise)
  northness   = cos(aspect) * sin(slope),  eastness = sin(aspect) * sin(slope)
                (-1..1; 0 on flat ground) - usable as linear model inputs
Outputs:
  data/terrain_guanacaste_nasadem_90m.tif  3 bands: elevation_m, slope_deg, aspect_deg (float32)
  data/terrain_cell.csv                     per H3 cell: mean elevation, slope, northness, eastness
  data/terrain_canton.csv                   per canton: same means
"""
import json
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.transform import from_bounds

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
W, S, E, N = -86.0, 9.6, -84.7, 11.25
RES = 3 / 3600
WIDTH, HEIGHT = round((E - W) / RES), round((N - S) / RES)
TRANSFORM = from_bounds(W, S, E, N, WIDTH, HEIGHT)


def hrefs():
    body = json.dumps({"collections": ["nasadem"], "bbox": [W, S, E, N], "limit": 50}).encode()
    req = urllib.request.Request("https://planetarycomputer.microsoft.com/api/stac/v1/search", data=body,
                                 headers={"Content-Type": "application/json"})
    feats = json.load(urllib.request.urlopen(req, timeout=120))["features"]
    tok = json.load(urllib.request.urlopen(
        "https://planetarycomputer.microsoft.com/api/sas/v1/token/nasadem", timeout=60))["token"]
    return [f"/vsicurl/{f['assets']['elevation']['href']}?{tok}" for f in feats]


def zonal(zone_ids, n, arrays):
    out = {}
    flat = zone_ids.ravel()
    for name, a in arrays.items():
        a = a.ravel()
        ok = (flat > 0) & np.isfinite(a)
        s = np.bincount(flat[ok], weights=a[ok], minlength=n + 1)
        c = np.bincount(flat[ok], minlength=n + 1)
        out[name] = np.where(c > 0, s / np.maximum(c, 1), np.nan)[1:]
    return out


def main():
    srcs = [rasterio.open(h) for h in hrefs()]
    dem, _ = merge(srcs, bounds=(W, S, E, N), res=RES, resampling=Resampling.bilinear)
    dem = dem[0].astype(np.float32)[:HEIGHT, :WIDTH]
    dem[dem < -100] = np.nan  # NASADEM nodata over sea is -32768

    lat = N - (np.arange(HEIGHT) + 0.5) * RES
    dy = RES * 110540.0
    dx = (RES * 111320.0 * np.cos(np.radians(lat)))[:, None]
    gy, gx = np.gradient(dem)
    dzdx = gx / dx
    dzdy = -gy / dy  # rows go north -> south
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    aspect = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360) % 360  # downslope direction, 0 = N
    flat = np.hypot(dzdx, dzdy) < 1e-6
    aspect[flat] = np.nan
    s_rad, a_rad = np.radians(slope), np.radians(np.nan_to_num(aspect))
    northness = np.where(flat, 0, np.cos(a_rad) * np.sin(s_rad))
    eastness = np.where(flat, 0, np.sin(a_rad) * np.sin(s_rad))

    prof = dict(driver="GTiff", height=HEIGHT, width=WIDTH, count=3, dtype="float32", crs="EPSG:4326",
                transform=TRANSFORM, nodata=np.nan, compress="deflate", predictor=3, tiled=True)
    with rasterio.open(DATA / "terrain_guanacaste_nasadem_90m.tif", "w", **prof) as dst:
        for i, (b, n) in enumerate([(dem, "elevation_m"), (slope, "slope_deg"), (aspect, "aspect_deg")], 1):
            dst.write(b.astype(np.float32), i)
            dst.set_band_description(i, n)

    arrays = {"elevation_m": dem, "slope_deg": slope, "northness": northness, "eastness": eastness}
    cell = gpd.read_file(DATA / "guanacaste_poblacion_kontur_h3_400m.geojson")[["h3", "geometry"]]
    z = rasterize(((g, i + 1) for i, g in enumerate(cell.geometry)), out_shape=(HEIGHT, WIDTH),
                  transform=TRANSFORM, fill=0, dtype="int32")
    res = zonal(z, len(cell), arrays)
    pd.DataFrame({"h3": cell.h3, **{k: np.round(v, 3) for k, v in res.items()}}).to_csv(
        DATA / "terrain_cell.csv", index=False)

    prov = gpd.read_file(DATA / "costa_rica_provincias_geoboundaries.geojson")
    cant = gpd.read_file(DATA / "costa_rica_cantones_geoboundaries.geojson")
    gte = prov.loc[prov.shapeISO == "CR-G"].geometry.union_all()
    cant = cant.loc[cant.geometry.representative_point().within(gte)].reset_index(drop=True)
    z = rasterize(((g, i + 1) for i, g in enumerate(cant.geometry)), out_shape=(HEIGHT, WIDTH),
                  transform=TRANSFORM, fill=0, dtype="int32")
    res = zonal(z, len(cant), arrays)
    out = pd.DataFrame({"canton": cant.shapeName, **{k: np.round(v, 3) for k, v in res.items()}})
    out.to_csv(DATA / "terrain_canton.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
