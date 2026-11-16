// Vigía Orbital website, laid out like the presentation:
//   view "forecast": satellite map with the 5-day panel over it (slides 1-2)
//   view "detail":   one day in detail, with the 5-day strip below (slide 3)
// Forecasts come from the live API (FastAPI) when it answers, otherwise from the saved
// files in site/data/ (rebuilt every morning by the Pages workflow).
const LV = {
  "Low": {c: "#2E9E6A", in: "#BFE8D2", s: 0.55, t: "#0F2236"},
  "Moderate": {c: "#E8C547", in: "#FFF1B8", s: 0.75, t: "#0F2236"},
  "High": {c: "#F08A24", in: "#FFD27A", s: 1.0, t: "#0F2236"},
  "Very high": {c: "#D2382C", in: "#F7B0A8", s: 1.1, t: "#FFFFFF"},
  "Extreme": {c: "#7E1B1B", in: "#E08A8A", s: 1.2, t: "#FFFFFF"},
};
const S = {mode: "latest", view: "forecast", canton: "CR501", day: 0, data: {}, meta: null, live: null};
const $ = id => document.getElementById(id);
const u = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--u")) || Math.min(innerWidth / 1920, innerHeight / 1080);
const U = () => matchMedia("(max-aspect-ratio: 1/1)").matches ? innerWidth / 1000 : Math.min(innerWidth / 1920, innerHeight / 1080);
const portrait = () => matchMedia("(max-aspect-ratio: 1/1)").matches;
const fmt = (iso, o) => new Date(iso + "T00:00:00Z").toLocaleDateString("en-GB", {timeZone: "UTC", ...o});
const pct = p => (p < 0.01 ? "<1" : Math.round(p * 100)) + " %";
const idx = p => (Math.round(p * 100 + 1e-9) / 100).toFixed(2);
// Flame sized in stage units, bigger with the risk (as in the deck)
const flame = (lvl, h) => {
  const L = LV[lvl];
  return `<svg style="height:calc(${h * L.s}*var(--u));width:calc(${h * L.s * 40 / 62}*var(--u))" viewBox="8 0 40 62" aria-label="${lvl} risk"><path d="M28 0c4 14 20 22 20 42a20 20 0 0 1-40 0c0-10 6-16 10-22 2 8 6 12 10 12C28 22 22 12 28 0z" fill="${L.c}"/><path d="M28 34c3 6 10 9 10 18a10 10 0 0 1-20 0c0-5 4-9 6-12 1 3 2 5 4 5 0-4-2-7 0-11z" fill="${L.in}"/></svg>`;
};
const pill = (lvl, cls, id) => `<span ${id ? `id="${id}"` : ""} class="${cls}" style="background:${LV[lvl].c};color:${LV[lvl].t}">${lvl}</span>`;

async function load() {
  const get = f => fetch("data/" + f).then(r => r.json());
  const [geo, latest, demo, meta] = await Promise.all([get("cantons.geojson"), get("latest.json"), get("demo.json"), get("meta.json")]);
  S.data = {latest, demo}; S.meta = meta; S.geo = geo;
  // What the reference satellite saw on each past day (so the badges never depend on the API)
  try {
    const fd = await get("fire_days.json"), t0 = Date.parse(fd.origin + "T00:00:00Z");
    S.fire = {through: fd.through, t0, sets: Object.fromEntries(Object.entries(fd.cantons).map(([k, v]) => [k, new Set(v)]))};
  } catch (e) { S.fire = null; }
  await tryLiveApi();
  initMap(geo);
  const sel = $("canton");
  sel.innerHTML = geo.features.map(f => f.properties).sort((a, b) => a.name.localeCompare(b.name))
    .map(p => `<option value="${p.canton_id}">${p.name} (Guanacaste)</option>`).join("");
  sel.onchange = () => { S.canton = sel.value; render(true); };
  $("m-latest").onclick = () => setMode("latest");
  $("m-demo").onclick = () => setMode("demo");
  const eve = $("eve");
  eve.max = S.data.latest.eve;
  if (!S.live) { eve.disabled = true; eve.parentElement.classList.add("off"); eve.parentElement.title = "Needs the live API, which is not answering right now"; }
  eve.onchange = () => eve.value && loadDate(eve.value);
  $("back").onclick = () => setView("forecast");
  $("prev").onclick = () => { if (S.day > 0) { S.day--; render(); } };
  $("next").onclick = () => { if (S.day < 4) { S.day++; render(); } };
  $("about-btn").onclick = () => $("about").showModal();
  $("about-close").onclick = () => $("about").close();
  $("ai-btn").onclick = () => $("ai").showModal();
  $("ai-close").onclick = () => $("ai").close();
  addEventListener("resize", () => { S.map.invalidateSize(); fit(); });
  renderAbout();
  setMode(new URLSearchParams(location.search).get("mode") === "demo" ? "demo" : "latest");
}

const fromApi = j => {
  const cantons = {};
  for (const c of j.cantons) cantons[c.canton_id] = {name: c.canton, eve: c.eve, days: c.days, conditions: c.conditions};
  return {eve: j.eve, cantons, inputs: j.inputs};
};

async function tryLiveApi() {
  const api = (window.VIGIA_API || "").replace(/\/$/, "");
  if (!api) return;
  try {
    const r = await fetch(api + "/forecast/all", {signal: AbortSignal.timeout(30000)});
    if (!r.ok) throw new Error(r.status);
    const j = await r.json();
    S.live = api;                                    // the API answers: any past date is available
    if (j.eve >= S.data.latest.eve) { S.data.latest = fromApi(j); S.liveLatest = true; }
  } catch (e) { console.warn("Live API unavailable, using the saved forecast", e); }
}

async function loadDate(d) {
  $("note").textContent = "Asking the API for " + fmt(d, {day: "numeric", month: "long", year: "numeric"}) + "…";
  try {
    const r = await fetch(`${S.live}/forecast/all?eve=${d}`, {signal: AbortSignal.timeout(30000)});
    if (!r.ok) throw new Error((await r.json()).detail || r.status);
    S.data.date = fromApi(await r.json());
    setMode("date");
  } catch (e) { $("note").textContent = "No forecast for that date: " + e.message; }
}

function initMap(geo) {
  S.map = L.map("map", {zoomSnap: 0.1, minZoom: 7, maxZoom: 11, zoomControl: false});
  L.control.zoom({position: "topleft"}).addTo(S.map);
  S.sat = L.tileLayer("", {maxNativeZoom: 9}).addTo(S.map);
  S.layer = L.geoJSON(geo, {
    onEachFeature: (f, l) => {
      l.on("click", () => { S.canton = f.properties.canton_id; render(true); });
      l.bindTooltip(f.properties.name, {permanent: true, direction: "center", className: "clabel"});
    }
  }).addTo(S.map);
}

// Keep the selected canton in the part of the map that the panels leave free
function fit() {
  const k = U(), sel = S.layer.getLayers().find(l => l.feature.properties.canton_id === S.canton);
  if (portrait()) { S.map.fitBounds(S.layer.getBounds(), {padding: [10, 10]}); return; }
  if (S.view === "detail") {
    S.map.fitBounds(sel.getBounds(), {paddingTopLeft: [40 * k, 190 * k], paddingBottomRight: [innerWidth - 880 * k, 330 * k], maxZoom: 10.2});
  } else {
    S.map.fitBounds(sel.getBounds().pad(0.6), {paddingTopLeft: [60 * k, 170 * k], paddingBottomRight: [60 * k, 540 * k], maxZoom: 9.6});
  }
}

function setMode(m) {
  S.mode = m;
  S.day = m === "demo" ? 4 : 0;
  if (m === "demo") S.canton = "CR501";
  $("m-latest").classList.toggle("on", m === "latest");
  $("m-demo").classList.toggle("on", m === "demo");
  $("eve").parentElement.classList.toggle("on", m === "date");
  if (m !== "date") $("eve").value = "";
  S.view = "forecast";
  document.body.className = "view-forecast";
  render(true);
}

function setView(v) {
  S.view = v;
  document.body.className = "view-" + v;
  render(true);
  if (portrait()) (v === "detail" ? document.querySelector(".det") : document.querySelector(".panel")).scrollIntoView({behavior: "smooth", block: "start"});
}

function satellite(eve) {
  // Newest image that surely exists: the eve, or yesterday (UTC) for today's forecast
  const y = new Date(Date.now() - 864e5).toISOString().slice(0, 10);
  const d = eve < y ? eve : y;
  const viirs = d >= "2018-01-05";                   // VIIRS NOAA-20 from 2018, MODIS Terra before
  const layer = viirs ? "VIIRS_NOAA20_CorrectedReflectance_TrueColor" : "MODIS_Terra_CorrectedReflectance_TrueColor";
  const url = `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer}/default/${d}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`;
  if (S.sat._url !== url) S.sat.setUrl(url);
  $("source").textContent = `Image: NASA GIBS · ${viirs ? "VIIRS NOAA-20" : "MODIS Terra"} true color, ${fmt(d, {day: "numeric", month: "short", year: "numeric"})} · Boundaries: geoBoundaries`;
}

const card = (d, i, opts) => `
  <button class="card${opts.first && i === 0 ? " first" : ""}${opts.sel === i ? " sel" : ""}" data-i="${i}">
    <span class="dow">${fmt(d.date, {weekday: "short"})}${opts.compact ? " " + fmt(d.date, {day: "numeric"}) : ""}</span>
    ${opts.compact ? "" : `<span class="date">${fmt(d.date, {day: "numeric", month: "short"})}</span>`}
    <span class="flame">${flame(d.level, opts.compact ? 46 : 80)}</span>
    ${pill(d.level, "lvl")}
    <span class="idx">Index: ${idx(d.prob)}${opts.compact && d.fire_observed ? " · fire ✓" : ""}</span>
    ${opts.compact || d.fire_observed == null ? "" : `<span class="seen${d.fire_observed ? "" : " none"}">${d.fire_observed ? "✓ fire detected" : "no fire"}</span>`}
  </button>`;

function render(refit) {
  const D = S.data[S.mode], sel = D.cantons[S.canton];
  if (S.fire) for (const d of sel.days) if (d.fire_observed == null && d.date <= S.fire.through)
    d.fire_observed = S.fire.sets[S.canton]?.has(Math.round((Date.parse(d.date + "T00:00:00Z") - S.fire.t0) / 864e5)) ? 1 : 0;
  const day = sel.days[S.day];
  const name = S.geo.features.find(f => f.properties.canton_id === S.canton).properties.name;
  $("canton").value = S.canton;
  satellite(D.eve);
  const when = fmt(D.eve, {weekday: "short", day: "numeric", month: "short", year: "numeric"});
  $("issued").textContent = S.mode === "latest" ? `Latest forecast · issued ${when} with the most recent satellite data` : `Issued on the evening of ${when}`;
  const inp = D.inputs || {};
  $("note").innerHTML = S.mode === "demo"
    ? "A real past week, forecast by a model trained <b>without any 2018 data</b>."
    : S.mode === "date"
      ? `Computed just now by the <a href="${S.live}/docs">API</a>. The badges show what the satellites detected afterwards. Past dates use the official model (trained on 2012–2025); only the Demo week is a strict blind test.`
      : S.liveLatest
        ? `<b>Live</b> from the <a href="${S.live}/docs">API</a>.` + (inp.recent_fire_through
          ? ` Fire data through ${fmt(inp.recent_fire_through, {day: "numeric", month: "short"})}; weather from ${fmt(inp.weather_as_of, {day: "numeric", month: "short"})}.` : "")
        : "Saved forecast, refreshed every morning.";

  S.layer.eachLayer(l => {
    const id = l.feature.properties.canton_id, c = D.cantons[id], on = id === S.canton;
    l.setStyle({fillColor: c ? LV[c.days[S.day].level].c : "#999", fillOpacity: on ? 0.5 : 0.38,
                color: "#FFFFFF", weight: on ? 4 : 1.2});
    l.getTooltip().getElement()?.classList.toggle("sel", on);
    if (on) l.bringToFront();
  });

  // View 1: the forecast panel
  $("place").textContent = `${name} (Guanacaste)`;
  $("cards").innerHTML = sel.days.map((d, i) => card(d, i, {first: S.mode !== "demo"})).join("");
  // View 2: the day in detail
  $("datebar").textContent = fmt(day.date, {weekday: "long", day: "numeric", month: "long", year: "numeric"});
  $("prev").disabled = S.day === 0; $("next").disabled = S.day === 4;
  $("bigflame").innerHTML = flame(day.level, 58);
  $("riskpill").outerHTML = pill(day.level, "risk-pill", "riskpill");
  $("riskidx").textContent = `Index: ${idx(day.prob)}`;
  const obs = $("obs"), seen = day.fire_observed;
  obs.hidden = seen == null;
  obs.className = "obs" + (seen ? "" : " none");
  obs.textContent = seen ? "✓ Fire detected" : "No fire detected";
  const c = sel.conditions, v = (x, un = "") => x == null ? "–" : x + un;
  $("cdate").textContent = "· NASA POWER, " + fmt(c.date || D.eve, {day: "numeric", month: "short"});
  const cells = a => a.map(([b, s]) => `<div class="cond"><b>${b}</b><small>${s}</small></div>`).join("");
  $("conds").innerHTML = cells([[`${v(c.t_max_c)}/${v(c.t_min_c)}°`, "Max / min °C"], [v(c.humidity_pct, " %"), "Humidity"], [v(c.wind_kmh), "Wind km/h"], [v(c.rain_mm, " mm"), "Rain 24 h"]]);
  $("inds").innerHTML = cells([[v(c.ndvi), "NDVI · greenness"], [v(c.ndmi), "NDMI · leaf moisture"], [v(c.days_without_rain), "Days without rain"]]);
  $("hist").innerHTML = `A normal year on this date: <b>${pct(day.normal_prob)}</b>. This year’s conditions: <b>${pct(day.prob)}</b>. Each factor below multiplies the odds of fire.`;
  $("drivers").innerHTML = [["Weather", day.x_weather], ["Vegetation", day.x_vegetation], ["Recent fire", day.x_recent_fire]]
    .map(([n, x]) => `<div class="drv"><b class="${x > 1.02 ? "up" : x < 0.98 ? "down" : "flat"}">×${x.toFixed(2)}</b><small>${n}</small></div>`).join("");
  $("stripcards").innerHTML = sel.days.map((d, i) => card(d, i, {compact: true, sel: S.day})).join("");

  document.querySelectorAll("#cards .card").forEach(b => b.onclick = () => { S.day = +b.dataset.i; setView("detail"); });
  document.querySelectorAll("#stripcards .card").forEach(b => b.onclick = () => { S.day = +b.dataset.i; render(); });
  if (refit) { S.map.invalidateSize(); fit(); }
}

function renderAbout() {
  const m = S.meta.metrics;
  $("metrics").innerHTML = [["+" + (m.bss_2013_2025 * 100).toFixed(1) + " %", "more accurate than an average year"],
    [m.years_bss_positive, "seasons better than the average year"],
    [m.auc_model_2013_2025.toFixed(3), "AUC (average year: " + m.auc_ref_2013_2025.toFixed(3) + ")"],
    ["+" + (m.lead_bss["5"] * 100).toFixed(1) + " %", "still better on day 5"]].map(([b, s]) => `<div class="stat"><b>${b}</b><small>${s}</small></div>`).join("");
  $("legend").innerHTML = S.meta.levels.map(([up, n], i, a) =>
    `<span><i style="background:${LV[n].c}"></i>${n} ${i ? Math.round(a[i - 1][0] * 100) : 0}${up > 1 ? " % +" : "–" + Math.round(up * 100) + " %"}</span>`).join("");
  $("runid").textContent = S.meta.run_id;
  $("apilink").href = (window.VIGIA_API || "").replace(/\/$/, "") + "/docs";
}

load();
