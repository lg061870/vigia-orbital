# Vigía Orbital

*"Desde el espacio, cuidamos nuestra tierra."*

NASA Space Apps Challenge 2026, San José, Costa Rica. Challenge: **Harmonization of MODIS and VIIRS Hot Spots**.

> Vigía Orbital convierte datos satelitales de NASA en un plan de temporada y una lista priorizada de incendios a atender, para que las brigadas de Guanacaste vayan donde realmente se necesitan.

This is a fire-season **planning** tool for Guanacaste. It is built for SINAC (Programa Nacional de Manejo del Fuego), Bomberos forestales, CNE and the municipalities. The engine is a harmonized MODIS + VIIRS hotspot record for 2012–2025. On top of it sit three pieces: a risk outlook by canton, triage of each alert as a likely agricultural burn or a likely wildfire, and a recurrence map for prevention. Everything runs offline.

## Repository layout

| Path | Contents |
|---|---|
| `data/` | Data kit (see table below). All EPSG:4326 (WGS84 lat/lon). |
| `imagenes_demo/` | NASA GIBS PNGs used as an offline basemap (`L.imageOverlay`). |
| `offline_libs/` | `leaflet-1.9.4-dist.zip` (Leaflet JS/CSS/images for the no-internet map). |
| `scripts/` | Data checks and processing scripts. |
| `outputs/` | Generated summaries (CSV). |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/sanity_check.py
```

## Data kit (`data/`)

| File | What it is | Source |
|---|---|---|
| `vigia_orbital_firms_costa_rica_2012_2025.csv` | 129,973 hotspots in Costa Rica, 2012–2025: MODIS (2012–2025), VIIRS S-NPP (2012–2025), VIIRS NOAA-20/JPSS-1 (2018–2025). Unified columns: `source` (`modis`, `viirs-snpp`, `viirs-jpss1`), `latitude`, `longitude`, `acq_date`, `acq_time`, `satellite`, `instrument`, `confidence`, `frp`, `daynight`, `type`, `bright_main` (MODIS `brightness` / VIIRS `bright_ti4`, K), `bright_secondary` (`bright_t31` / `bright_ti5`), `scan`, `track`, `version` | NASA FIRMS Country Yearly Summary (standard processing) |
| `nasa_power_guanacaste_daily_2012_2025.csv` | Daily weather 2012–2025 at 13 points: 11 Guanacaste canton seats, plus Puntarenas and a San José reference. `T2M`, `T2M_MAX`, `T2M_MIN` (°C), `PRECTOTCORR` (mm/day), `RH2M` (%), `WS2M` (m/s), `GWETTOP` (surface soil wetness, 0–1). Date = `YEAR` + `DOY` | NASA POWER API, AG community |
| `noaa_oni_2012_2026.csv` | Oceanic Niño Index by 3-month season, 2012 to ASO 2026. `oni_anomaly` ≥ +0.5 = El Niño. ASO 2026 = +2.46 (strong El Niño developing) | NOAA CPC `oni.ascii.txt` |
| `costa_rica_provincias_geoboundaries.geojson` | 7 provinces (simplified) | geoBoundaries gbOpen CRI ADM1 |
| `costa_rica_cantones_geoboundaries.geojson` | 83 cantons | geoBoundaries gbOpen CRI ADM2 |
| `costa_rica_distritos_geoboundaries.geojson` | 472 districts | geoBoundaries gbOpen CRI ADM3 |
| `costa_rica_areas_protegidas_osm.geojson` | 132 protected areas / national parks / reserves as MultiPolygon, with OSM tags (`name`, `protect_class`, …). Converted from Overpass JSON | OpenStreetMap |
| `esa_worldcover_2021_guanacaste_~35m.tif` | Land-cover GeoTIFF, bbox lon −86.0 to −84.7, lat 9.6 to 11.25, 4096 × 5199 px (~35 m/px, nearest-neighbour from 10 m). Classes: 10 trees, 20 shrub, 30 grassland, 40 cropland, 50 built-up, 60 bare, 80 water, 90 herbaceous wetland, 95 mangrove | ESA WorldCover 2021 v200 (tile `N09W087`) |

Not in the repo: `osm_areas_protegidas_costa_rica_overpass.json` is the raw Overpass backup of the protected areas. It stays in the project Drive folder and isn't needed, because the GeoJSON above has the same content.

### How the files got here (provenance)

- The geoBoundaries GeoJSONs, protected areas, NASA POWER CSV and ONI CSV were copied byte-for-byte from the project's Drive kit (downloaded 12 Nov 2026).
- The FIRMS CSV was rebuilt from the FIRMS country files (`https://firms.modaps.eosdis.nasa.gov/data/country/{modis,viirs-snpp,viirs-jpss1}/<year>/…_Costa_Rica.csv`, 2012–2025). The files were concatenated and their columns renamed as above. The result matches the Drive original in row count (129,973), byte size (11,711,241) and leading rows.
- The WorldCover GeoTIFF was regenerated from the official ESA WorldCover 2021 v200 10 m tile (`esa-worldcover.s3.eu-central-1.amazonaws.com`), with a nearest-neighbour resample to the bbox above.

### Demo images (`imagenes_demo/`)

Source: NASA GIBS WMS (`epsg4326/best`). They serve as an offline basemap (Leaflet `L.imageOverlay` with these bboxes).

| File | Content | Bbox |
|---|---|---|
| `guanacaste_viirs_truecolor_focos_2024-03-20.png` | VIIRS S-NPP true colour + hotspots | lat 9.4–11.3, lon −86.4 to −84.4 |
| `santa_cruz_hls_landsat30m_focos_2024-03-17.png` | HLS Landsat 30 m + VIIRS hotspots, Santa Cruz | lat 10.15–10.35, lon −85.824 to −85.375 |
| `costa_rica_viirs_truecolor_2024-03-20.png` | All of Costa Rica, VIIRS true colour | lat 8.0–11.3, lon −86.0 to −82.5 |

[Worldview demo view (Santa Cruz, 17 Mar 2024)](https://worldview.earthdata.nasa.gov/?v=-85.82456140350877,10.15,-85.37543859649122,10.35&l=Reference_Labels_15m,Coastlines_15m,VIIRS_SNPP_Thermal_Anomalies_375m_All,VIIRS_NOAA20_Thermal_Anomalies_375m_All,HLS_S30_Nadir_BRDF_Adjusted_Reflectance,HLS_L30_Nadir_BRDF_Adjusted_Reflectance,VIIRS_SNPP_CorrectedReflectance_TrueColor&lg=true&t=2024-03-17-T12%3A00%3A00Z)

### Notes

- Suomi NPP stopped delivering data on 2 Nov 2026, so recent data should come from NOAA-20 / NOAA-21.
- VIIRS (375 m) detects roughly 4–5× more points than MODIS (1 km) over the same area; see `outputs/cr_detections_by_year_source.csv`.

## Data sources and citations

- **NASA FIRMS**: MODIS Collection 6.1 and VIIRS 375 m active fire detections (S-NPP, NOAA-20), standard processing. This project acknowledges the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS), part of NASA's Earth Science Data and Information System (ESDIS), and LANCE/EOSDIS.
- **NASA POWER**: These data were obtained from the NASA Langley Research Center (LaRC) POWER Project, funded through the NASA Earth Science/Applied Science Program.
- **NOAA CPC**: Oceanic Niño Index (ONI), Climate Prediction Center.
- **geoBoundaries**: Runfola, D. et al. (2020). geoBoundaries: A global database of political administrative boundaries. *PLoS ONE* 15(4): e0231866. CC BY 4.0.
- **OpenStreetMap**: © OpenStreetMap contributors, ODbL. Retrieved via the Overpass API.
- **ESA WorldCover**: Zanaga, D. et al. (2022). ESA WorldCover 10 m 2021 v200. CC BY 4.0.
- **NASA GIBS / Worldview**: imagery from NASA's Global Imagery Browse Services (GIBS), part of EOSDIS.
- **Leaflet** 1.9.4 (BSD-2-Clause).

## License

MIT (code). The data keep the licences of their sources listed above.
