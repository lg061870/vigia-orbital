# Vigía Orbital – data dictionary (`data/vigia_orbital.duckdb`)

Built by `scripts/build_db.py`. Diagram: `docs/data_model.puml`.

**Size column:** storage per value. Fixed types: DOUBLE, BIGINT and TIMESTAMP are 8 bytes; INTEGER 4 bytes; UTINYINT and BOOLEAN 1 byte. For VARCHAR it's the longest value in the data, in characters. For BLOB it's the largest value, in bytes.

**Common conventions**
- Geometries are stored as `geom_wkb`: Well-Known Binary, coordinates in EPSG:4326 (longitude/latitude, WGS84).
- Distances and areas are computed in CRTM05 (EPSG:5367, Costa Rica's metric projection) and then converted to km or km².
- **Distance to nearest X** = the minimum straight-line distance from the point to any feature of X (to the edge of a polygon, or 0 if inside it), in metres ÷ 1000, rounded to 0.001 km.

---

## 1. `canton` (83 rows): one row per canton of Costa Rica

| Field | Type | Size | What goes in there / formula |
|---|---|---|---|
| canton_id | VARCHAR | 17 | **PK.** Official canton code from UNFPA (ADM2_PCODE), e.g. `CR501` = Liberia. Cantons missing from UNFPA 2021 get `GB-<name>` (`GB-Puerto_Jimenez`, `GB-Rio_Cuarto`). Matched by name after removing accents and lower-casing, plus 5 manual aliases (Quepos→Aguirre, Sarchí→Valverde Vega, etc.). |
| name | VARCHAR | 19 | Name as in geoBoundaries, without accents (`Canas`). Same spelling as in `weather_day.canton` and `vi_canton_8day.canton`. |
| name_es | VARCHAR | 19 | Official Spanish name with accents (`Cañas`), from UNFPA. Use it for display. |
| province | VARCHAR | 10 | Province containing the canton's representative point (a point guaranteed inside the polygon). |
| ac_code | VARCHAR | 4 | **FK → conservation_area.** SINAC conservation area containing the canton's representative point (`AC01` = ACG). Every Guanacaste canton is ≥ 96.5% inside one area (`data/guanacaste_canton_area_conservacion.csv`). |
| area_km2 | DOUBLE | 8 B | Polygon area in CRTM05 ÷ 10⁶, rounded to 0.1 km². |
| pop_2021 | DOUBLE | 8 B | Population 2021 = Σ `T_TL` of the canton's districts (UNFPA). NULL for the two `GB-` cantons. |
| geom_wkb | BLOB | 40,156 B | Canton polygon (geoBoundaries ADM2). |

## 2. `conservation_area` (10 rows): SINAC conservation areas

| Field | Type | Size | What goes in there |
|---|---|---|---|
| ac_code | VARCHAR | 4 | **PK.** SINAC code, `AC01`–`AC10` (no Isla del Coco). |
| ac_name | VARCHAR | 19 | Name, e.g. `Guanacaste`, `Tempisque`, `Arenal Tempisque`. |
| ac_abbr | VARCHAR | 6 | Abbreviation: `ACG`, `ACT`, `ACAT`, … |
| geom_wkb | BLOB | 61,309 B | Polygon from SIREFOR (2021), simplified to 20 m. |

## 3. `protected_area` (132 rows): parks, reserves and refuges (OpenStreetMap)

| Field | Type | Size | What goes in there |
|---|---|---|---|
| osm_id | INTEGER | 4 B | **PK.** OpenStreetMap id. |
| name | VARCHAR | 76 | Name, e.g. `Parque Nacional Diriá`. |
| boundary | VARCHAR | 14 | OSM tag: `national_park`, `protected_area` or NULL. |
| leisure | VARCHAR | 14 | OSM tag, e.g. `nature_reserve`. |
| protect_class | VARCHAR | 2 | OSM protection class (2 = national park, 6 = managed resource area, 98 = World Heritage site, …). |
| protection_title | VARCHAR | 25 | Free-text title from OSM, when present. |
| geom_wkb | BLOB | 164,342 B | MultiPolygon. |

## 4. `cell` (6,816 rows): H3 hexagons of ~400 m covering Guanacaste

The spatial grid for recurrence, triage and the map. It's the same grid as the Kontur population data (H3 resolution 8, ~0.74 km² per cell).

| Field | Type | Size | What goes in there / formula |
|---|---|---|---|
| h3 | VARCHAR | 15 | **PK.** H3 cell index at resolution 8, e.g. `886d1d...`. |
| population | INTEGER | 4 B | Estimated people in the cell (Kontur 2023), rounded. |
| canton_id | VARCHAR | 5 | **FK → canton.** Canton containing the cell centre. NULL if the centre is just outside Costa Rica's boundary (the grid includes a 2 km buffer). |
| landcover_centroid | UTINYINT | 1 B | ESA WorldCover 2021 class at the cell centre: 10 trees, 20 shrub, 30 grassland, 40 cropland, 50 built-up, 60 bare, 80 water, 90 wetland, 95 mangrove. It's a single-pixel sample (~35 m), not the majority class. |
| dist_protected_area_km | DOUBLE | 8 B | Distance from the cell centre to the nearest protected area (0 if inside). |
| dist_road_km | DOUBLE | 8 B | Distance to the nearest vehicle road or track (OSM). |
| dist_fire_station_km | DOUBLE | 8 B | Straight-line distance to the nearest fire station (OSM; 14 stations). Not road distance. |
| dist_populated_place_km | DOUBLE | 8 B | Distance to the nearest populated place (OSM point). |
| geom_wkb | BLOB | 125 B | Hexagon polygon. |

## 5. `facility` (1,352 rows): points of interest for alerts

| Field | Type | Size | What goes in there |
|---|---|---|---|
| id | VARCHAR | 17 | **PK.** OSM id from the HOT export. |
| kind | VARCHAR | 15 | `fire_station`, `health` or `populated_place`. |
| subtype | VARCHAR | 17 | Health: `hospital`, `clinic`, `doctors`, `dentist`, `pharmacy`. Places: `city`, `town`, `village`, `hamlet`, `neighbourhood`, `isolated_dwelling`. NULL for fire stations. |
| name | VARCHAR | 56 | Name, when mapped. |
| geom_wkb | BLOB | 21 B | Point (a polygon is converted to a point inside it). |

## 6. `population_district` (478 rows): UNFPA population 2021 by district

| Field | Type | Size | What goes in there |
|---|---|---|---|
| ADM1_ES / ADM1_PCODE | VARCHAR | 10 / 3 | Province name / code (`CR5` = Guanacaste). |
| ADM2_ES / ADM2_PCODE | VARCHAR | 19 / 5 | Canton name / code. **FK → canton.canton_id.** |
| ADM3_ES / ADM3_PCODE | VARCHAR | 25 / 7 | District name / code. **PK** = ADM3_PCODE. |
| F_TL, M_TL, T_TL | BIGINT | 8 B | Female, male and total population 2021. |

## 7. `detection` (129,973 rows): every satellite fire detection, 2012–2025

The raw FIRMS columns, plus the links added by the build script.

| Field | Type | Size | What goes in there / formula |
|---|---|---|---|
| detection_id | BIGINT | 8 B | **PK.** Sequential id (row order of the CSV). |
| source | VARCHAR | 11 | `modis` (Terra + Aqua, 1 km), `viirs-snpp` (Suomi NPP, 375 m), `viirs-jpss1` (NOAA-20, 375 m). |
| latitude, longitude | DOUBLE | 8 B | Centre of the detection pixel, WGS84. |
| acq_date | VARCHAR | 10 | Acquisition date, `YYYY-MM-DD`, **UTC**. |
| acq_time | VARCHAR | 4 | Acquisition time, `HHMM`, UTC (kept as text to keep leading zeros). |
| acq_datetime_utc | TIMESTAMP | 8 B | = `acq_date` + `acq_time`. Costa Rica local time = UTC − 6 h. |
| satellite | VARCHAR | 5 | `Terra`, `Aqua`, `N` (S-NPP) or `N20` (NOAA-20). |
| instrument | VARCHAR | 5 | `MODIS` or `VIIRS`. |
| confidence | VARCHAR | 3 | MODIS: 0–100 (as text). VIIRS: `l` low, `n` nominal, `h` high. |
| frp | DOUBLE | 8 B | Fire Radiative Power, megawatts (0–691.8 here), a measure of fire intensity. |
| daynight | VARCHAR | 1 | `D` day / `N` night pass. |
| type | BIGINT | 8 B | FIRMS inferred hot-spot type: **0 = presumed vegetation fire** (128,201), 1 = active volcano (706), 2 = other static land source, e.g. industry (872), 3 = offshore (194). **Fire analyses should use `type = 0` only.** |
| bright_main | DOUBLE | 8 B | Brightness temperature, kelvin: MODIS `brightness` (band 21/22, 4 µm) or VIIRS `bright_ti4` (I4, 3.7 µm). |
| bright_secondary | DOUBLE | 8 B | MODIS `bright_t31` (11 µm) or VIIRS `bright_ti5` (I5, 11 µm). |
| scan, track | DOUBLE | 8 B | Actual pixel size in km along scan and track. It grows towards the edge of the swath (0.32–4.8 km here). |
| version | DOUBLE | 8 B | Processing collection/version (MODIS 6.03, 6.2, 61.03; VIIRS 2.0). |
| canton_id | VARCHAR | 17 | **FK → canton.** Canton containing the point. NULL for 455 points at sea or on the border. |
| h3 | VARCHAR | 15 | **FK → cell.** `h3.latlng_to_cell(latitude, longitude, 8)`. Outside Guanacaste the code exists but has no row in `cell`. |
| in_protected_area | BOOLEAN | 1 B | TRUE if the point falls inside any protected-area polygon. |
| dist_protected_area_km | DOUBLE | 8 B | Distance to the nearest protected area (0 if inside). |

## 8. `weather_day` (66,482 rows): NASA POWER daily weather

13 points × 5,114 days (1 Jan 2012 – 31 Dec 2025). The points are the 11 Guanacaste canton seats plus Puntarenas and a San José reference. Values are POWER's ~0.5° grid cell containing each point, so neighbouring cantons can share similar values.

| Field | Type | Size | What goes in there / formula |
|---|---|---|---|
| canton | VARCHAR | 12 | Point name (geoBoundaries spelling; `San Jose ref` is a reference point). |
| canton_id | VARCHAR | 5 | **FK → canton.** NULL for `San Jose ref`. |
| lat, lon | DOUBLE | 8 B | Coordinates of the canton seat used for the query. |
| YEAR, DOY | BIGINT | 8 B | Year and day of year (1–366), as delivered by POWER. |
| date | TIMESTAMP | 8 B | = 1 January of YEAR + (DOY − 1) days. |
| T2M | DOUBLE | 8 B | Mean air temperature at 2 m, °C. |
| T2M_MAX / T2M_MIN | DOUBLE | 8 B | Daily maximum / minimum temperature at 2 m, °C. |
| PRECTOTCORR | DOUBLE | 8 B | Precipitation, bias-corrected, mm/day. |
| RH2M | DOUBLE | 8 B | Relative humidity at 2 m, %. |
| WS2M | DOUBLE | 8 B | Wind speed at 2 m, m/s. |
| GWETTOP | DOUBLE | 8 B | Surface soil wetness (top layer), 0 = dry to 1 = saturated. |

## 9. `vi_canton_8day` (6,908 rows): MODIS vegetation indices per canton

11 cantons × 628 composites (Terra + Aqua, one every 8 days, Nov 2011 – Dec 2025).

| Field | Type | Size | What goes in there / formula |
|---|---|---|---|
| date | TIMESTAMP | 8 B | First day of the 16-day compositing window (the composite covers date … date + 15 days). |
| sensor | VARCHAR | 3 | `MOD` (Terra) or `MYD` (Aqua). |
| canton / canton_id | VARCHAR | 10 / 5 | Canton (FK → canton). |
| ndvi_mean | DOUBLE | 8 B | Mean NDVI of the canton's clear pixels. **NDVI = (NIR − Red) / (NIR + Red)**, from −1 to 1. Green, healthy vegetation is ~0.7–0.9; dry vegetation and bare soil are lower. Taken from the product's own NDVI layer (MODIS bands 1 and 2). |
| nbr_mean | DOUBLE | 8 B | Mean NBR. **NBR = (NIR − SWIR2) / (NIR + SWIR2)**, with NIR = MODIS band 2 (0.86 µm) and SWIR2 = band 7 (2.1 µm). High = healthy, moist vegetation. It drops after burning (less NIR, more SWIR) and also in drought. |
| valid_share | DOUBLE | 8 B | Share of the canton's pixels that are clear: `pixel_reliability` ∈ {0 good, 1 marginal}; clouds, shadow and snow are excluded. Values < 0.3 mean the composite is mostly cloudy, so don't trust the mean. |

How pixels are prepared: both MODIS tiles (h09v07, h09v08) are re-projected to a 0.0025° grid (~275 m) with nearest-neighbour resampling. Pixels failing the reliability test are masked before averaging.

## 10. `oni` (177 rows): Oceanic Niño Index

| Field | Type | Size | What goes in there / formula |
|---|---|---|---|
| season | VARCHAR | 3 | 3-month window: `DJF`, `JFM`, … `NDJ`. |
| year | BIGINT | 8 B | Year as listed by NOAA CPC (for `NDJ` it's the year of Nov–Dec). |
| center_month | BIGINT | 8 B | Middle month of the window (DJF → 1 … NDJ → 12). Used to join to a calendar month. |
| total_sst_c | DOUBLE | 8 B | Mean sea-surface temperature in the Niño 3.4 region (5°N–5°S, 120°–170°W), °C. |
| oni_anomaly | DOUBLE | 8 B | **ONI = 3-month running mean of the SST anomaly in Niño 3.4** (relative to a 30-year base period, per NOAA CPC). ≥ +0.5 = El Niño, ≤ −0.5 = La Niña, ≥ +1.5 = strong El Niño. |

## 11. `raster_catalog` (15 rows): images kept as GeoTIFF files

| Field | Type | Size | What goes in there |
|---|---|---|---|
| path | VARCHAR | 44 | **PK.** Path relative to the repo root. |
| kind | VARCHAR | 12 | `modis_season` or `landcover`. |
| season_year | DOUBLE | 8 B | Season year for `modis_season` (2012–2025), NULL otherwise. |
| bands | VARCHAR | 50 | Comma-separated band names, in band order. |
| scale | DOUBLE | 8 B | Multiply stored values by this (1e-4 for MODIS indices). |

**Bands of `data/modis_season/season_<Y>.tif`** (int16, ×10,000, ~275 m). "Median" means the per-pixel median of all clear composites whose start date falls in the window:

| Band | Name | Formula |
|---|---|---|
| 1 | NDVI_pre | median NDVI, 1 Dec (Y−1) – 31 Jan Y (start of the dry season) |
| 2 | NBR_pre | median NBR, same window |
| 3 | NDVI_peak | median NDVI, 1–31 March Y (peak of the dry season) |
| 4 | NBR_post | median NBR, 16 Apr – 31 May Y (end of the season) |
| 5 | dNBR | **NBR_pre − NBR_post**. Positive = vegetation lost moisture or burned during the season. |
| 6 | dNBR_anom | **dNBR − median(dNBR over 2012–2025) for that pixel**. It removes the normal dry-season leaf drop, which is large in Guanacaste's deciduous dry forest, so what remains is change beyond normal: the likely burn signal. > 0.1 is used as "unusual change". |

## 12. View `canton_day` (61,368 rows): canton × day, 2012–2025

The table the forecast model trains on. It's a view: computed on the fly from the tables above, never stored.

| Field | Type | What goes in there / formula |
|---|---|---|
| canton_id, canton | VARCHAR | Canton (12 points: 11 Guanacaste cantons + Puntarenas). |
| date | TIMESTAMP | Day. |
| T2M … GWETTOP | DOUBLE | That day's weather from `weather_day`. |
| vi_date | TIMESTAMP | Start date of the MODIS composite used: the **latest composite with date ≤ day and valid_share ≥ 0.3** (an "as-of join"). On a cloudy stretch it carries forward the last clear view. |
| ndvi_mean, nbr_mean, vi_valid_share | DOUBLE | Values of that composite. NULL for Puntarenas, which is outside the MODIS area. |
| oni_anomaly | DOUBLE | ONI of the 3-month window centred on the day's month. |

Not yet in it: fire counts and rolling features (days since rain, 30/60/90-day rain sums, NDVI anomaly vs the same date in other years). Those are built at the event.

---

## Planned tables (built at the event; fields may change)

### `cell_day`: harmonized fire record (the challenge deliverable)
| Field | Type | Plan |
|---|---|---|
| h3, date | VARCHAR, DATE | **PK.** Cell and local date (UTC − 6 h). |
| n_modis, n_viirs_snpp, n_viirs_noaa20 | INTEGER | Count of `type = 0` detections per sensor in that cell and day. |
| fire_present_harmonized | BOOLEAN | Sensor-independent "fire in this cell today". The rule is fixed at the event, from matching MODIS and VIIRS over 2012–2025 (for example, cross-calibrating VIIRS-only days so that 2012–2017 is comparable with 2018+). |

### `forecast`: the "pronóstico del fuego"
| Field | Type | Plan |
|---|---|---|
| canton_id, issue_date, lead_day | VARCHAR, DATE, INTEGER | **PK.** Forecast for canton, made on issue_date, for issue_date + lead_day (1–10). |
| expected_vs_normal | DOUBLE | Predicted harmonized fire activity ÷ the 2012–2025 average for that canton and week of the year (1.0 = normal). |
| danger_class | VARCHAR | Bands of expected_vs_normal, e.g. bajo / moderado / alto / muy alto / extremo. Thresholds set at the event. |
| p10, p90 | DOUBLE | 80% range of the prediction. |

### `alert`: triage of each new detection
| Field | Type | Plan |
|---|---|---|
| detection_id | BIGINT | **PK, FK → detection.** |
| priority | VARCHAR | `verificar primero` / `verificar después`, from the score below. |
| reason_protected_area | VARCHAR | From `dist_protected_area_km` (closer = higher priority). |
| reason_recurrence | VARCHAR | Number of earlier seasons with fire in the same cell and similar dates. Recurring = more likely a routine burn; new place = higher priority. |
| reason_landcover | VARCHAR | WorldCover class (forest = higher priority; cropland or pasture = lower). |
| reason_season | VARCHAR | Date relative to the dry season and to that cell's usual burn dates. |
| message_text | VARCHAR | Plain-text alert for brigades, ≤ 5 KB. |
