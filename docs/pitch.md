# Pitch — Vigía Orbital (2 min, español)

All figures are reproducible with `scripts/season_stats.py` (see the README, "What the data says so far"). Detections = VIIRS 375 m in the 11 Guanacaste cantons, 2012–2025, unless stated otherwise.

## Hook (0:00–0:30)

> Guanacaste concentra el 63 % de los focos de calor de Costa Rica, y el 88 % ocurre en solo tres meses: febrero, marzo y abril. Pero ningún índice climático por sí solo predice qué tan dura será una temporada. Las dos peores temporadas en Guanacaste fueron 2013, un año neutro, y 2022, un año de La Niña. El Niño explica poco (r = 0,40). Por eso Vigía Orbital combina los 14 años de historia de cada cantón con señales reales de sequía, semana a semana.

Speaker notes (for Q&A, do not read aloud):
- 63.4 % = all sensors (82,461 / 129,973). 88 % = VIIRS S-NPP (87.9 %); all sensors 86.8 %.
- The two worst seasons (2013, 2022) are by VIIRS. With MODIS, the top three are 2013, 2015 and 2016.
- r = 0.40 is with DJF ONI, n = 14, p = 0.16 (not significant). r² = 0.16, so ONI accounts for about 16 % of the variation between seasons.

## Outline

1. **0:00–0:30 Hook** (above).
2. **0:30–0:50 Harmonization (the challenge).** VIIRS detects about 4–5× more points than MODIS for the same fires, and the ratio changes by year and by canton. A single conversion factor doesn't work, so the detections are matched on a common grid by day. The result is one comparable 2012–2025 record. Suomi NPP stopped in Nov 2026, and NOAA-20 continues it about 1:1.
3. **0:50–1:15 Season plan by canton.** Risk map plus a 1–2 week outlook.
4. **1:15–1:35 Triage and alert.** Prioritized list: likely agricultural burn vs likely wildfire near a protected area. Shows the WhatsApp alert (< 5 KB) on a brigade phone.
5. **1:35–1:50 2027 outlook (secondary line).**
   > Las dos temporadas con El Niño fuerte en nuestro registro, 2016 y 2024, estuvieron por encima de la mediana. Hoy el ONI está en +2,46, pero el rango sigue siendo amplio: entre 2.600 y 6.800 focos con 80 % de probabilidad. Eso va desde una temporada por debajo de lo normal hasta un récord. Por eso no basta con mirar El Niño: hay que planificar cantón por cantón.
6. **1:50–2:00 Close and next step.**
   > Siguiente paso: validar con los informes de área quemada del SINAC. Vigía Orbital convierte datos satelitales de NASA en un plan de temporada y una lista priorizada de incendios a atender, para que las brigadas de Guanacaste vayan donde realmente se necesitan.

## Numbers behind the 2027 line

| Item | Value |
|---|---|
| 2016 (DJF ONI +2.50) | 4,320 detections, rank 4 of 14 |
| 2024 (DJF ONI +1.84) | 4,029 detections, rank 6 of 14 |
| Median season | 3,892 |
| Range 2012–2025 | 1,241–5,935 |
| Linear fit at ONI +2.46 (ASO 2026) | ≈ 4,700; 80 % PI 2,600–6,800; 95 % PI 1,300–8,000 |

## Do not say

- "2024 was the worst season" (it ranks 6th of 14).
- "El Niño predicts the season" or "2027 will be severe" as a certainty.
