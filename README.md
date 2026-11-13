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
| `docs/pitch.md` | 2-minute pitch outline (Spanish), with the source of every number. |

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
| `costa_rica_areas_conservacion_sirefor_2021.geojson` | SINAC conservation areas, 10 polygons (ACG, ACT, ACAT, ACAHN, ACTo, ACLAC, ACLAP, ACC, ACOPAC, ACOSA; the marine Isla del Coco area is not included). Columns `ac_code`, `ac_name`, `ac_abbr`. Simplified to 20 m and converted from CRTM05 (EPSG:5367) to WGS84 | SIREFOR (SINAC/MINAE) WFS layer `SIREFORV2:aprovechamiento_areas_conservacion_numpermisos_2021` |
| `guanacaste_canton_area_conservacion.csv` | Each Guanacaste canton's conservation area and the share of the canton's area inside it (96.5–99.8%). ACG: Liberia, La Cruz. ACT: Santa Cruz, Carrillo, Nicoya, Hojancha, Nandayure. ACAT: Bagaces, Cañas, Abangares, Tilarán | Derived (`scripts/build_conservation_areas.py`) |
| `raw/sirefor_limites_areas_conservacion_2021_CRTM05.zip` | Original shapefile of the layer above, as downloaded (EPSG:5367) | SIREFOR WFS |
| `guanacaste_poblacion_kontur_h3_400m.geojson` | Population on H3 hexagons of ~400 m (6,816 hexagons; about 423,000 people in Guanacaste). Columns `h3`, `population` | Kontur Population, 2023-11-01 release (CC BY), via HDX |
| `costa_rica_poblacion_distritos_unfpa_2021.csv` | Population 2021 by district (ADM3) for all Costa Rica, by sex and 5-year age group. Codes `ADM1_PCODE`…`ADM3_PCODE`, names `ADM1_ES`…`ADM3_ES`. Guanacaste total: 399,409 | UNFPA Subnational Population Statistics (CC BY-IGO), via HDX |
| `guanacaste_caminos_hotosm.geojson` | Vehicle roads in Guanacaste, including tracks (20,090 lines; footways, paths and steps removed). Columns `id`, `name`, `highway`, `surface` | OpenStreetMap via HOT export, 2026-11-03 (ODbL), via HDX |
| `guanacaste_poblados_hotosm.geojson` | Populated places as points (1,027). Columns `id`, `name`, `place`, `population` | OpenStreetMap via HOT export, 2026-11-03 (ODbL), via HDX |
| `guanacaste_salud_hotosm.geojson` | Health facilities as points (311: clinics, pharmacies, doctors, dentists, hospitals) | OpenStreetMap via HOT export, 2026-11-03 (ODbL), via HDX |
| `guanacaste_bomberos_hotosm.geojson` | Fire stations (`amenity=fire_station`) as points: 13 in Guanacaste plus Monteverde's, just over the border | OpenStreetMap via HOT points-of-interest export, 2026-11-03 (ODbL), via HDX |
| `modis_ndvi_nbr_canton_8day_2012_2025.csv` | Mean NDVI and NBR per Guanacaste canton for every MODIS composite (Terra + Aqua, one every 8 days, Nov 2011–Dec 2025; 628 composites), plus the share of valid (cloud-free) pixels | MODIS MOD13Q1/MYD13Q1 v061 via Planetary Computer; `scripts/build_modis_indices.py` |
| `modis_season/season_<YEAR>.tif` | One raster per dry season, 2012–2025, ~275 m, EPSG:4326, int16 ×10000. Bands: NDVI_pre (Dec–Jan), NBR_pre, NDVI_peak (March), NBR_post (16 Apr–May), dNBR (pre − post), and dNBR_anom (dNBR minus the 2012–2025 per-pixel median, i.e. change beyond normal dry-season leaf loss) | same |

Not in the repo: `osm_areas_protegidas_costa_rica_overpass.json` is the raw Overpass backup of the protected areas. It stays in the project Drive folder and isn't needed, because the GeoJSON above has the same content.

### How the files got here (provenance)

- The geoBoundaries GeoJSONs, protected areas, NASA POWER CSV and ONI CSV were copied byte-for-byte from the project's Drive kit (downloaded 12 Nov 2026).
- The FIRMS CSV was rebuilt from the FIRMS country files (`https://firms.modaps.eosdis.nasa.gov/data/country/{modis,viirs-snpp,viirs-jpss1}/<year>/…_Costa_Rica.csv`, 2012–2025). The files were concatenated and their columns renamed as above. The result matches the Drive original in row count (129,973), byte size (11,711,241) and leading rows.
- The WorldCover GeoTIFF was regenerated from the official ESA WorldCover 2021 v200 10 m tile (`esa-worldcover.s3.eu-central-1.amazonaws.com`), with a nearest-neighbour resample to the bbox above.
- The conservation-area boundaries were downloaded on 13 Nov 2026 from SIREFOR's WFS (`https://www.sirefor.go.cr/GeoserviciosSIREFOR/wfs`, `typeName=SIREFORV2:aprovechamiento_areas_conservacion_numpermisos_2021`, `outputFormat=SHAPE-ZIP`). SIREFOR doesn't publish a standalone boundary layer, so these come from a 2021 harvest-permit layer that has one polygon per conservation area. Its permit, tree and timber-volume columns are dropped. The 2022 and 2023 versions of that layer exist but are empty. SIREFOR has no fire statistics.
- The HDX layers were downloaded on 13 Nov 2026 and clipped to Guanacaste (province polygon + 2 km buffer) by `scripts/build_hdx_layers.py`. The script lists every source URL, keeps the raw files in `data/raw_hdx/` (git-ignored, re-downloaded if missing), and turns polygon features into points. OSM coverage of roads, places, health facilities and fire stations is volunteer-mapped and may be incomplete.
- MODIS indices: NDVI comes from the product's own layer, and NBR = (NIR − MIR)/(NIR + MIR) uses MODIS band 7 (2.1 µm, SWIR2). Pixels whose `pixel_reliability` isn't good or marginal are masked. Both tiles (h09v07, h09v08) are warped to a 0.0025° grid. The full 8-day stack (~330 MB) is in `data/raw_modis/` (git-ignored); the script rebuilds it. At 250 m, dNBR blurs small burns, so use the USGS/MTBS severity thresholds (calibrated for 30 m Landsat) only as a rough guide.

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
- The `canton` names in the NASA POWER CSV were normalized to match the geoBoundaries ADM2 names (underscores → spaces: `La Cruz`, `Santa Cruz`, `San Jose ref`) with `scripts/normalize_power_cantons.py`. No other value changed. `scripts/check_power_join.py` verifies four things: all 11 Guanacaste cantons have a series, each canton-seat point falls inside its own canton polygon, the 2 reference points sit outside Guanacaste, and every series has one row per day (5,114).

## Database (`data/vigia_orbital.duckdb`)

A single DuckDB file (10.5 MB) that ties the data kit together and works offline. Rebuild it with `.venv/bin/python scripts/build_db.py`, which takes ~40 s; the script is the source of truth. Geometries are stored as WKB blobs (EPSG:4326). Rasters stay as GeoTIFF files and are listed in `raster_catalog`.

| Table | Rows | Key / contents |
|---|---|---|
| `canton` | 83 | `canton_id` = UNFPA ADM2 code (CR501–CR511 for Guanacaste; `GB-<name>` for Puerto Jiménez and Río Cuarto, which UNFPA 2021 lacks), names with accents, province, `ac_code`, area, population 2021 |
| `conservation_area` | 10 | SINAC areas (SIREFOR) |
| `protected_area` | 132 | OSM protected areas |
| `detection` | 129,973 | FIRMS points + `canton_id`, `h3` (H3 resolution 8, ~400 m, same grid as Kontur), `in_protected_area`, `dist_protected_area_km` |
| `cell` | 6,816 | Guanacaste H3 cells: population, `canton_id`, WorldCover class at the centroid, distance to protected area / road / fire station / populated place |
| `facility` | 1,352 | fire stations, health facilities, populated places (OSM) |
| `weather_day` | 66,482 | NASA POWER daily per canton seat (+ Puntarenas and San José reference points) |
| `vi_canton_8day` | 6,908 | MODIS NDVI / NBR per canton and composite |
| `oni` | 177 | ONI with `center_month` |
| `population_district` | 478 | UNFPA 2021 totals by district |
| `raster_catalog` | 15 | GeoTIFF paths and band names |
| view `canton_day` | 61,368 | canton × day 2012–2025: weather + latest clear MODIS composite (as-of join, ≥30% clear pixels) + ONI. Puntarenas has weather only (outside the MODIS area). No fire counts yet: the harmonized count is built at the event. |

To browse it: the DuckDB CLI's built-in web UI (`duckdb -ui data/vigia_orbital.duckdb`), DBeaver (DuckDB driver), or from Python (`duckdb.connect("data/vigia_orbital.duckdb")`).

## What the data says so far

Reproduce with `scripts/sanity_check.py` and `scripts/season_stats.py`. Season = calendar year, and "detections" = VIIRS S-NPP 375 m inside the 11 Guanacaste cantons, unless stated otherwise.

- **Concentrated in space and time.** Guanacaste holds 63.4% of Costa Rica's 2012–2025 detections (82,461 of 129,973, all sensors). 87.9% of its VIIRS detections fall in February–April (86.8% across all sensors; 80.0% for MODIS alone).
- **No single climate index predicts season severity.** By VIIRS, the two worst seasons were 2013 (DJF ONI −0.24, neutral) and 2022 (−0.76, La Niña). The correlation between season detections and DJF ONI is r = 0.40 (r² = 0.16, p = 0.16, n = 14). The correlation stays at r ≈ 0.40–0.43 with a Nov–Oct season or with MODIS instead of VIIRS. MODIS ranks the seasons differently (2013, 2015, 2016 top), so the "two worst" statement is specific to VIIRS.
- **The strong El Niño seasons in the record were above the median.** 2016 (DJF ONI +2.50) had 4,320 detections (rank 4 of 14). 2024 (+1.84) had 4,029 (rank 6). The median season is 3,892, and the full range is 1,241–5,935.
- **2027 outlook, with honest uncertainty.** The latest ONI is +2.46 (ASO 2026). A simple linear fit of season detections on DJF ONI gives about 4,700 detections at that ONI. Its 80% prediction interval is 2,600–6,800, and its 95% interval is 1,300–8,000. In other words, it is consistent with anything from a below-median season to a record one. ENSO alone cannot plan a season, so the model must also use each canton's history and weekly dryness. 2027 detections will come from NOAA-20/21, because S-NPP stopped in Nov 2026. NOAA-20 tracks S-NPP about 1:1 in 2019–2025 (for example 4,019 vs 4,029 in Guanacaste in 2024).
- **Vegetation dryness is the strongest signal so far, and it's available before the season.** Across the 14 seasons, mean NDVI over the Guanacaste cantons correlates with season detections at r = −0.80 in January (p = 0.001), −0.81 in the first half of February, and −0.84 in March (p < 0.001): greener vegetation, fewer fires. For comparison, ONI gives r = 0.40. The March figure is partly simultaneous with the fires, but the January one comes before the season. The burn-scar signal (share of the province with dNBR_anom > 0.1) correlates more weakly (r = 0.48, p = 0.08) because MODIS's 250 m blurs small burns. See `outputs/gte_season_modis_vs_fires.csv`.

## Next steps

- Build during the event (14–15 Nov): harmonization, the risk model (built by canton and added up to SINAC's conservation areas ACG, ACT and ACAT, which is SINAC's planning unit), alert triage and the offline Leaflet app.
- **Validate against SINAC burned-area reports** (seasonal reports from the Programa Nacional de Manejo del Fuego). Compare reported area burned and number of fires per season and canton with the harmonized detection record, and with the triage labels. This validation is not a prerequisite for the demo.

## Data sources and citations

- **MODIS MOD13Q1 / MYD13Q1 v061** (Didan, K., NASA EOSDIS LP DAAC), accessed via Microsoft Planetary Computer.
- **NASA FIRMS**: MODIS Collection 6.1 and VIIRS 375 m active fire detections (S-NPP, NOAA-20), standard processing. This project acknowledges the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS), part of NASA's Earth Science Data and Information System (ESDIS), and LANCE/EOSDIS.
- **NASA POWER**: These data were obtained from the NASA Langley Research Center (LaRC) POWER Project, funded through the NASA Earth Science/Applied Science Program.
- **NOAA CPC**: Oceanic Niño Index (ONI), Climate Prediction Center.
- **geoBoundaries**: Runfola, D. et al. (2020). geoBoundaries: A global database of political administrative boundaries. *PLoS ONE* 15(4): e0231866. CC BY 4.0.
- **OpenStreetMap**: © OpenStreetMap contributors, ODbL. Retrieved via the Overpass API.
- **SIREFOR / SINAC**: conservation-area boundaries from the Sistema de Información de Recursos Forestales (SINAC, MINAE), WFS layer `aprovechamiento_areas_conservacion_numpermisos_2021`.
- **Kontur Population** (2023), CC BY; **UNFPA** Subnational Population Statistics (2021), CC BY-IGO; **Humanitarian OpenStreetMap Team** exports of OpenStreetMap data, ODbL. All via the Humanitarian Data Exchange (data.humdata.org).
- **ESA WorldCover**: Zanaga, D. et al. (2022). ESA WorldCover 10 m 2021 v200. CC BY 4.0.
- **NASA GIBS / Worldview**: imagery from NASA's Global Imagery Browse Services (GIBS), part of EOSDIS.
- **Leaflet** 1.9.4 (BSD-2-Clause).

## License

MIT (code). The data keep the licences of their sources listed above.
