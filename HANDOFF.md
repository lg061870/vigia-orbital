# HANDOFF — Vigía Orbital (NASA Space Apps 2026, San José, Costa Rica)

Read this first. It replaces a long earlier session. Last updated 14 Nov 2026.

## Who / event
- Guillermo Jiménez (Systematica Labs, one-person company: write "I", never "we"). Team "Vigía Orbital" — *"Desde el espacio, cuidamos nuestra tierra"*.
- Challenge: **Harmonization of MODIS and VIIRS Hot Spots**.
- In person Sat–Sun 14–15 Nov, 9 am–8 pm, Universidad Fidélitas. **Submission closes Sun 15 Nov, 11:59 pm (UTC−6).**
- Hackathon rule: the analysis and app are built during the event. Everything below is setup and data prep.
- UI and pitch in Spanish; code and comments in English. Never invent data or numbers; cite sources (README).
- Venue Wi-Fi will fail: **everything must run offline** (local data, local Leaflet, NASA images as basemap). Precompute anything that needs internet.

## Product (current vision)
**"Pronóstico del fuego" for Guanacaste**: a fire-danger forecast that works like a weather forecast, for SINAC, Bomberos, CNE and municipalities. It's built on a harmonized MODIS + VIIRS fire record (2012–2025) plus weather and vegetation dryness.
1. **Forecast:** expected fire activity vs normal for each canton, 1–10 days ahead, rolled up to SINAC conservation areas (ACG, ACT, ACAT), with an 80% range.
2. **Triage of each detection:** "verificar primero / verificar después" (never a binary burn/wildfire label), with 4 visible reasons: distance to protected area, recurrence at that place, land cover, timing vs dry season. MAG burn permits are out of scope.
3. **Recurrence map** for prevention.
4. **Delivery:** one responsive offline web app (Leaflet). The desktop command-post view is the hero; mobile is a phone layout plus a plain-text WhatsApp/Telegram alert (≤ 5 KB). No native app.

**Demo story (judges love story and colour):** a forecast **replay of March 2024**. "On 10 March 2024 Vigía Orbital would have forecast very high danger for Santa Cruz/Carrillo; here's what happened." The forecast map animates day by day, the real detections appear, and it ends on burn scars (HLS image; dNBR). It closes with the 2027 season outlook. The replay uses observed weather, so say "con el clima observado".

UI mockup (private): https://claude.ai/artifact/WZhoxYtu2QVSNXR48CYEmW. Dark command-post look; orange = verificar primero, blue = verificar después.

## Findings so far (all reproducible; numbers are VIIRS S-NPP in the 11 Guanacaste cantons unless stated)
- Guanacaste = 63.4% of Costa Rica's detections (82,461 / 129,973). 87.9% happen in Feb–Apr.
- **Vegetation dryness is the best signal: January NDVI vs season detections r = −0.80 (p = 0.001)**; early Feb −0.81; March −0.84.
- El Niño (DJF ONI) is weak: r = 0.40 (p = 0.16). The worst seasons were 2013 (neutral) and 2022 (La Niña). **2024 was NOT the worst season** (6th of 14). Strong El Niño seasons 2016 and 2024 were above the median (3,892). 2027 outlook at ONI +2.46: ≈ 4,700, 80% range 2,600–6,800.
- VIIRS/MODIS ≈ 4.6× on average, but it varies by year (3.5–5.4) and canton (2.75–5.8): **no single conversion factor**; harmonize by matching on grid × day. NOAA-20 ≈ S-NPP 1:1 since 2019 (S-NPP stopped Nov 2026; use NOAA-20/21).
- Use only FIRMS `type = 0` (706 volcano, 872 industrial, 194 offshore detections exist). FIRMS dates are UTC; Costa Rica = UTC−6.
- NASA POWER is a ~0.5° grid: neighbouring cantons have similar weather.

## Repo
- GitHub `lg061870/vigia-orbital`. **Branch `setup/data`** has everything; the working branch is `claude/vigia-orbital-space-apps-klgtt2`. Don't push to `main` without asking.
- `data/vigia_orbital.duckdb` (10.5 MB): the database. Rebuild with `python scripts/build_db.py`.
- Docs: `README.md` (files, provenance, citations, findings), `docs/data_dictionary.md` (every table and field, formulas), `docs/data_model.puml` (ER diagram), `docs/pitch.md` (Spanish pitch outline; update it to the forecast story).
- Scripts: `sanity_check.py`, `season_stats.py`, `check_power_join.py`, `build_conservation_areas.py`, `build_hdx_layers.py`, `build_modis_indices.py`, `build_db.py`.
- Not in git (rebuilt by scripts if needed): `data/raw_modis/` (8-day MODIS stack, ~330 MB; needs Planetary Computer: `planetarycomputer.microsoft.com` and `modiseuwest.blob.core.windows.net`), `data/raw_hdx/`.
- Python 3.13, `requirements.txt` (pandas, geopandas, rasterio, shapely, scikit-learn, folium, duckdb, h3, …).
- FIRMS API key: in the environment variable `FIRMS_MAP_KEY` if needed. Never commit it.

## Build plan for the event
**Saturday**
1. 9–10: Offline check (Wi-Fi off), `pip install -r requirements.txt`, open the DB.
2. 10–12:30: **Harmonization** → `cell_day` (H3 res 8 × local date; per-sensor counts; `fire_present_harmonized`). Validate MODIS vs VIIRS consistency across 2012–2025 and make 2012–2017 comparable with 2018+. One chart for the pitch.
3. 13:30–16:30: **Forecast model** on `canton_day` + harmonized counts: rolling features (days since rain, 30/60/90-day rain, humidity, max temp, wind, soil wetness, NDVI anomaly vs the same date in other years, ONI, seasonality, canton history). Targets: activity in the next 1–10 days vs normal. Simple baseline (climatology) vs gradient boosting; validate leaving one season out; report skill vs climatology honestly. Also compute an FWI-style danger index if time allows.
4. 16:30–18:30: **Triage** → `alert` table + Spanish alert text generator.
5. 18:30–20: Precompute the March 2024 replay (forecasts issued daily 1–31 Mar 2024) and export JSON/GeoJSON for the app.

**Sunday**
6. 9–12:30: **Offline Leaflet app** (Spanish): animated 10-day forecast map, replay timeline, conservation-area panel, prioritized detection list, phone layout, alert preview. Basemap = `imagenes_demo/` PNGs via `L.imageOverlay` (bboxes in README); Leaflet from `offline_libs/`.
7. 13:30–15: Demo polish; optional 30 m dNBR hero map of Santa Cruz (Landsat/HLS, before/after 17 Mar 2024).
8. 15–16: Full offline test, phone check.
9. 16–18: 2-minute pitch (Spanish), slides, backup video.
10. 18–23:59: Submission: Space Apps project page, demo link/video, data and resources list.

## Pitch lines (Spanish, data-backed)
- "Guanacaste concentra el 63 % de los focos de calor de Costa Rica, y el 88 % ocurre en solo tres meses."
- "Ningún índice climático por sí solo predice la temporada… pero la sequedad de la vegetación en enero sí anticipa qué tan dura será (r = −0,80)."
- "Vigía Orbital convierte datos satelitales de NASA en un pronóstico del fuego y una lista priorizada de incendios a atender, para que las brigadas de Guanacaste vayan donde realmente se necesitan."
- Next step: "validar con los informes de área quemada del SINAC". **Don't say:** "2024 fue la peor temporada", or "2027 será severa" stated as a certainty.
