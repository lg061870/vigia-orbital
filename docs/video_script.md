# Vigía Orbital: video script (English, about 3 minutes)

Narration is first person ("I"). About 400 words; at a natural pace that is just under 3 minutes, including the clicks. Every number comes from `docs/briefing.md`.

Slide numbers refer to the deck in Present mode. Tabs to have open before recording:

- **Tab A:** the deck, on slide 1, in Present mode
- **Tab B:** https://lg061870.github.io/vigia-orbital/
- **Tab C:** https://lg061870-vigia-orbital-api.hf.space/api/sms?canton=Liberia&eve=2018-01-18

| # | Time | On screen | Say |
|---|---|---|---|
| 1 | 0:00–0:15 | **Slide 1** (today's forecast) | This is Vigía Orbital: a wildfire forecast for Guanacaste, Costa Rica. Like a weather forecast, but for fires. Today the risk is low, because the rainy season isn't over. So let's turn back the clock. |
| 2 | 0:15–0:35 | **Slide 2** (demo week). Click as you say "turn back the clock". | January 2018. It's Thursday evening, the 18th. It has just rained, so Friday and Saturday are Moderate. As the land dries, the risk climbs to High on Tuesday the 23rd. The model never saw 2018 when it made this forecast. |
| 3 | 0:35–0:50 | **Slide 3** (Tuesday 23) | Tuesday: High, 39 percent. And that day, NASA's satellites did detect fire in Liberia. A normal year gives this date 45 percent. Rain on the eve lowered it; dry vegetation and recent fire raised it. |
| 4 | 0:50–1:15 | **Tab B, the website.** Show the map, click "Demo week · Jan 2018", click the Tue 23 card, click Bagaces. Then **Tab C**, the text message. | And it's live. This is the website: every canton of Guanacaste, coloured by risk, for the next five days. Click a canton and it explains why. Behind it, an open API computes the forecast on request with the newest NASA fire data, and sends it as a text message under one kilobyte, for brigades with a weak signal. |
| 5 | 1:15–1:40 | **Slide 6** (harmonization) | The challenge was harmonizing MODIS and VIIRS. VIIRS sees three and a half to five times more fires than MODIS, and the ratio changes every year. Every new satellite inflates the raw counts. So I use one reference satellite per period, and I count fire days per canton, not detections. NOAA-21 matches Suomi NPP within four percent, so the record continues. |
| 6 | 1:40–2:00 | **Slide 7** (formula), then **slide 8** (coefficients) at "Drier weather" | The model is a logistic regression, one for each day ahead. It starts from what is normal for that canton and week, then adjusts for weather, vegetation and recent fire, all from open NASA data. Drier weather than normal multiplies the odds by 1.68. |
| 7 | 2:00–2:25 | **Slide 9** (validation) | Does it work? I tested it on every season from 2013 to 2025, each one forecast blind. It is 8.4 percent more accurate than an average year, and up to 21 percent in the worst seasons. When it says 90 percent or more, fire happens 96 percent of the time. On 2026, it tied with the average year. |
| 8 | 2:25–2:45 | **Slide 10** (impact) | Guanacaste holds 63 percent of Costa Rica's fire detections, most of them in just three months. With five days of warning, SINAC and the brigades can put crews where the risk is, and stand down when the rains come. |
| 9 | 2:45–3:00 | **Slide 12** (notebook and QR) | It isn't perfect: next, I need to validate it with SINAC's field reports. But everything is open: the data, the code, and a notebook that reproduces every number. Vigía Orbital: NASA data, turned into five days of warning. |

Slides 4, 5, 11 and 13 are skipped in the video; they stay in the deck for questions.

## If it runs long
- Cut shot 6 (formula and coefficients): saves about 20 seconds.
- In shot 4, skip the Bagaces click: saves about 5 seconds.

## Before recording
- Open Tab C a minute early: the free API goes to sleep and the first visit wakes it.
- Reload Tab B (Ctrl+F5) and check the cards show today's forecast.
- Browser at 100 % zoom, full screen, notifications off.
