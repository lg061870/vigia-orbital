# Vigía Orbital: briefing for Q&A practice

A one-page reference for rehearsing the pitch and answering judges' questions. Every number comes from the official run `20261115T152753Z` (`data/results/`) or the presentation's speaker notes (`docs/deck/project/slides/`). If a number is not here, look it up rather than estimating it.

## The project in one breath
- **Event:** NASA Space Apps Challenge 2026, San José, Costa Rica. Challenge: *Harmonization of MODIS and VIIRS Hot Spots*.
- **Team:** Vigía Orbital, Guillermo Jiménez (Systematica Labs, one person, so always say "I", never "we").
- **Product:** a 5-day fire-risk forecast for the 11 cantons of Guanacaste, "a weather forecast for fires". For each canton and each of the next 5 days it gives the probability that satellites detect a vegetation fire, plus a level: Low <10 %, Moderate 10–30 %, High 30–50 %, Very high 50–70 %, Extreme ≥70 %.
- **Live:**
  - website https://lg061870.github.io/vigia-orbital/
  - API https://lg061870-vigia-orbital-api.hf.space/api/docs
  - code and data https://github.com/lg061870/vigia-orbital
  - notebook (Colab) https://colab.research.google.com/github/lg061870/vigia-orbital/blob/main/notebooks/vigia_orbital_modelo.ipynb

## Why it matters
- Guanacaste holds **63 %** of Costa Rica's fire detections, **88 %** of them in February–April.
- **Users:** SINAC's fire program and brigades (where to position crews), firefighters and CNE (when to scale up or stand down), municipalities (when to time prevention messages and burn controls).
- **Delivery:** a text message under 1 KB that works with a weak signal. The API's `/sms` endpoint produces it.
- In May the model sees the rains coming, **23 %** better than the calendar.

## Harmonization (the challenge itself)
- **Four satellites:** MODIS (since 2000, 1 km pixels) and three VIIRS instruments (375 m pixels): Suomi NPP from 2012, NOAA-20 from 2018, NOAA-21 from 2023.
- **The problem:**
  - VIIRS S-NPP sees **3.5× to 5.4×** as many fires as MODIS (Costa Rica, 2012–2025: 3.5 in 2023, 5.4 in 2019).
  - That ratio changes by year and canton, so no single conversion factor works.
  - Each new satellite makes raw counts jump: more satellites, not more fire.
- **The solution:**
  - one reference satellite per period: S-NPP through 2025, NOAA-20 from 2026;
  - count **fire days per canton** (yes/no per local date) instead of raw detections;
  - keep only vegetation fires (FIRMS `type 0`);
  - convert UTC to local time (UTC−6).
- **Hand-over check:** NOAA-21 matches S-NPP within ±4 % per year (2023–2025), so the record continues.
- **Scale:** almost 158,000 fire detections and about 2,000 MODIS image composites.

## The model
- **Type:** logistic regression, "normal + adjustment", with one model per lead day k = 1…5:
  `P(fire on day t+k) = σ(β0 + βH·H + βC·C + βV·V + βF·F + βT·T)`
- **Inputs:**
  - **H**: history. Log-odds of fire for this canton and week of the year, 2012–2025 (the "normal year").
  - **C**: weather vs normal (NASA POWER): days without rain, max temperature, wind, humidity (−), soil moisture (−), 30-day rain (−).
  - **V**: vegetation vs normal (MODIS): NDVI and NDMI anomalies.
  - **F**: fire in the canton in the last 7 days.
  - **T**: terrain, the canton's mean slope (NASADEM). It adds nothing at canton level.
- **5-day model coefficients:** const −0.034, H 1.072, C 0.516, V −0.236, F 0.146, T 0.000.
- **Why logistic regression:** interpretable (each factor multiplies the odds), calibrated probabilities, and robust with 14 seasons of data.
- **Indicators:** NDVI = greenness, NDMI = leaf water, NBR = burn index. NBR is shown as a burn-scar indicator but is not a model input. Source: MODIS MOD13Q1/MYD13Q1 and MOD09A1/MYD09A1 v061 via Microsoft Planetary Computer, cloud-free pixels only, averaged per canton.

## Validation
- **Method:** leave-one-season-out, 2013–2025. Each season is forecast by a model trained on all the other years.
- **Results:**
  - Brier skill vs the canton-and-week climatology: **+8.4 %**.
  - AUC **0.932** vs 0.919 for climatology.
  - Positive skill in **12 of 14** seasons. Biggest gains in the worst seasons: 2013 +21 %, 2022 +17 %, 2024 +15 %.
  - By lead day: **+7.8 % / 6.8 / 6.3 / 5.8 / 5.4 %** for days 1 to 5.
  - Reliability: when it forecast ≥90 %, fire happened **96 %** of the time (7,900 canton-days).
- **Honest result:** on the 2026 season, a true test it never saw, it **tied** with climatology (skill 0.006). It was a season with nothing unusual for the conditions to explain.

## Demo week (real past week, model trained without any 2018 data)
- **Setup:** Liberia, forecast issued on the evening of Thu 18 Jan 2018. It had just rained.
- **Forecast:** Fri 0.22 Moderate · Sat 0.26 Moderate · Sun 0.31 High · Mon 0.32 High · **Tue 23: 0.39 High, and fire was detected that day**. No fire Fri–Mon.
- **Tuesday explained:**
  - normal risk for that date 45 % (fire on 23 January in 7 of the other 13 years);
  - weather ×0.65, because of rain and humidity on the eve;
  - vegetation ×1.18, slightly drier than normal;
  - recent fire ×1.25;
  - result: 39 %.
- **Eve conditions:** 28.9/22.7 °C, 79 % humidity, 14.6 km/h wind, 1.8 mm rain. NDVI 0.64 (normal 0.65), NBR 0.44 (normal 0.43). NDMI 0.11 in the dataset (the slide shows 0.10).
- **Latest forecast** (issued 12 Nov 2026, rainy season): Liberia Low, 1–2 % a day.

## Limits (say them before judges ask)
- A light rain can make it too optimistic for a few days (Liberia, May 2024).
- MODIS vegetation products arrive weeks late.
- It works at canton level, where terrain adds nothing.
- "Fire" means a satellite detection, so small fires and fires under clouds are missed.
- It has not yet been compared with SINAC field reports, and it tied climatology in 2026.

## Next steps
- a minimum-risk rule while vegetation stays dry;
- daily VIIRS reflectance for fresher vegetation;
- 400 m hexagons (grid and data already built);
- the Canadian Fire Weather Index;
- a conservation-area view for SINAC;
- validation with SINAC and the national weather service, ideally a pilot with one brigade.

## Sources (all open)
- **NASA:** FIRMS (MODIS, VIIRS S-NPP / NOAA-20 / NOAA-21), POWER (daily weather), MODIS MOD13Q1/MYD13Q1 and MOD09A1/MYD09A1 via Microsoft Planetary Computer, NASADEM, GIBS/Worldview, ARSET "Using the Fire Mapping Tools to Map Fires".
- **NOAA:** El Niño index.
- **Others:** ESA WorldCover, SINAC SIREFOR, geoBoundaries, HDX (OpenStreetMap/HOT, Kontur, UNFPA population).
- **Tools:** Leaflet, FastAPI.

Full citations are in `README.md`.

## Likely judge questions (short answers)
- **Why not just convert MODIS counts to VIIRS?** The ratio swings from 3.5 to 5.4 by year and also varies by canton. A fixed factor would invent trends. Fire days from one reference satellite don't.
- **Why not deep learning?** 14 seasons × 11 cantons is small data. A logistic model is calibrated, explainable to a brigade chief, and validated season by season.
- **Did the model see the demo week?** No. The demo uses a model trained without any 2018 data.
- **Is 8 % a lot?** It is skill on top of an already strong baseline (the canton-and-week normal, AUC 0.919). It is largest in bad seasons, when it matters most.
- **What happens when Suomi NPP is gone?** NOAA-20 is the reference from 2026, and NOAA-21 matches S-NPP within ±4 %.
- **How would SINAC use it tomorrow?** The website for planners, the API for their systems, and the SMS for brigades in the field.
- **What was built during the hackathon?** The analysis, model, validation, website and API. Everything is reproducible from the notebook (`PUBLISH = False` makes re-runs safe).
