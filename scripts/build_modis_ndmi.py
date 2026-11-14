"""NDMI (vegetation moisture) for Guanacaste, Nov 2011 - today (data prep).

NDMI = (NIR - SWIR1) / (NIR + SWIR1), with NIR = MODIS band 2 (0.86 um) and
SWIR1 = band 6 (1.64 um). The MOD13Q1 product used for NDVI/NBR has no band 6, so
NDMI comes from MOD09A1 / MYD09A1 v061 (8-day surface reflectance, 500 m) via
Planetary Computer. Clear-pixel mask from sur_refl_state_500m: cloud state
(bits 0-1) = 00 clear, no cloud shadow (bit 2), no internal cloud (bit 10).
Pixels are warped to the same 0.0025 deg grid as the NDVI/NBR stack.

Outputs:
  data/raw_modis_ndmi/<date>_<sensor>.tif   int16 NDMI x10000 (git-ignored)
  data/modis_ndmi_canton_8day.csv            mean NDMI / clear share per canton and composite
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_modis_indices as m  # shared grid, token, STAC helpers, canton zones  # noqa: E402

RAW = m.DATA / "raw_modis_ndmi"
LAST_YEAR = 2026


def search(year):
    body = {"collections": ["modis-09A1-061"], "bbox": [m.W, m.S, m.E, m.N],
            "datetime": f"{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z", "limit": 250}
    feats = m.http_json(m.STAC, body)["features"]
    return [f for f in feats if f["id"].split(".")[2] in ("h09v07", "h09v08")]


def process(key, tiles, token):
    out = RAW / f"{key}.tif"
    if out.exists():
        return
    ndmi = np.full((m.HEIGHT, m.WIDTH), m.NODATA, np.int16)
    for f in tiles:
        tok = token.get()
        state, _ = m.read_band(f["assets"]["sur_refl_state_500m"]["href"], tok, Resampling.nearest)
        b2, _ = m.read_band(f["assets"]["sur_refl_b02"]["href"], tok, Resampling.nearest)
        b6, _ = m.read_band(f["assets"]["sur_refl_b06"]["href"], tok, Resampling.nearest)
        s = state.astype(np.int64)
        clear = ((s & 0b11) == 0) & (((s >> 2) & 1) == 0) & (((s >> 10) & 1) == 0)
        nir, sw = b2.astype(np.float32), b6.astype(np.float32)
        den = nir + sw
        ok = clear & (b2 > 0) & (b6 > 0) & (den > 0)
        val = np.where(ok, np.round((nir - sw) / np.where(den == 0, 1, den) * 10000), m.NODATA).astype(np.int16)
        fill = ok & (ndmi == m.NODATA)
        ndmi[fill] = val[fill]
    prof = dict(driver="GTiff", height=m.HEIGHT, width=m.WIDTH, count=1, dtype="int16", crs="EPSG:4326",
                transform=m.TRANSFORM, nodata=m.NODATA, compress="deflate", predictor=2, tiled=True)
    with rasterio.open(out, "w", **prof) as dst:
        dst.write(ndmi, 1)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    token = m.Token()
    groups = {}
    for year in range(2011, LAST_YEAR + 1):
        for f in search(year):
            groups.setdefault(f"{f['properties']['start_datetime'][:10]}_{f['id'][:3]}", []).append(f)
    keys = sorted(k for k in groups if k >= "2011-11-01")
    print(len(keys), "composites", flush=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, _ in enumerate(ex.map(lambda k: process(k, groups[k], token), keys), 1):
            if i % 50 == 0:
                print(f"{i}/{len(keys)}", flush=True)

    zones, names = m.canton_zones()
    rows = []
    for f in sorted(RAW.glob("*.tif")):
        d, sensor = f.stem.split("_")
        with rasterio.open(f) as src:
            a = src.read(1)
        for i, name in enumerate(names):
            z = zones == i + 1
            v = z & (a != m.NODATA)
            rows.append({"date": d, "sensor": sensor, "canton": name,
                         "ndmi_mean": round(float(a[v].mean()) / 1e4, 4) if v.any() else None,
                         "valid_share": round(float(v.sum() / z.sum()), 3)})
    out = m.DATA / "modis_ndmi_canton_8day.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(out.name, len(rows), "rows")


if __name__ == "__main__":
    main()
