// Vigía Orbital website: a dashboard for the Risk of Fire Index.
// Forecasts come from the live API (FastAPI) when it answers, otherwise from the saved files in
// site/data/ (rebuilt every morning by the Pages workflow). Fire detections come from static files.
const LV = {
  "Low": "#3E9E6A", "Moderate": "#D9AE2B", "High": "#E7862E", "Very high": "#D4502C", "Extreme": "#9F2A2A",
};
const S = {mode: "latest", canton: "CR501", day: 0, data: {}, meta: null, live: null, bg: "sat"};
const $ = id => document.getElementById(id);
const fmt = (iso, o) => new Date(iso + "T00:00:00Z").toLocaleDateString("en-GB", {timeZone: "UTC", ...o});
const pct = p => (p < 0.01 ? "<1" : Math.round(p * 100)) + " %";
const idx = p => (Math.round(p * 100 + 1e-9) / 100).toFixed(2);

// Line icons (24 × 24, stroke = currentColor)
const P = {
  flame: '<path d="M12 3c.8 3 5 5.2 5 10.2A5 5 0 0 1 7 13.5c0-2.6 1.6-4.2 2.6-5.6.4 1.9 1.4 3 2.4 3 .1-2.9-1.4-4.9 0-7.9z"/>',
  temp: '<path d="M10 14.5V5a2 2 0 1 1 4 0v9.5a4 4 0 1 1-4 0z"/><path d="M12 10v6"/>',
  drop: '<path d="M12 3.5s6 6.4 6 10.5a6 6 0 0 1-12 0c0-4.1 6-10.5 6-10.5z"/>',
  wind: '<path d="M3 9h11a3 3 0 1 0-3-3M3 15h15a3 3 0 1 1-3 3M3 12h8"/>',
  rain: '<path d="M7 15a4 4 0 0 1-.6-8A6 6 0 0 1 18 8.5a3.5 3.5 0 0 1-.5 6.5H7z"/><path d="M8 18l-1 2.5M12 18l-1 2.5M16 18l-1 2.5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
  leaf: '<path d="M5 19c0-8 5-13 14-14-1 9-6 14-14 14z"/><path d="M5 19l7-7"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
};
const icon = (name, color) => `<svg class="ico" viewBox="0 0 24 24" ${color ? `style="color:${color}"` : ""} aria-hidden="true">${P[name]}</svg>`;
const flameFor = lvl => `<svg viewBox="0 0 24 24" aria-hidden="true" style="fill:${LV[lvl]}26;stroke:${LV[lvl]};stroke-width:1.7;stroke-linejoin:round">${P.flame}</svg>`;

async function load() {
  const get = f => fetch("data/" + f).then(r => r.json());
  const [geo, latest, demo, meta] = await Promise.all([get("cantons.geojson"), get("latest.json"), get("demo.json"), get("meta.json")]);
  S.data = {latest, demo}; S.meta = meta; S.geo = geo;
  try {   // days on which the reference satellite saw fire, per canton (so past days show what happened)
    const fd = await get("fire_days.json"), t0 = Date.parse(fd.origin + "T00:00:00Z");
    S.fire = {through: fd.through, t0, sets: Object.fromEntries(Object.entries(fd.cantons).map(([k, v]) => [k, new Set(v)]))};
  } catch (e) { S.fire = null; }
  await tryLiveApi();
  initMap(geo);

  const sel = $("canton");
  sel.innerHTML = geo.features.map(f => f.properties).sort((a, b) => a.name.localeCompare(b.name))
    .map(p => `<option value="${p.canton_id}">${p.name}, Guanacaste</option>`).join("");
  sel.onchange = () => { S.canton = sel.value; render(); };
  $("m-latest").onclick = () => setMode("latest");
  $("m-demo").onclick = () => setMode("demo");
  const eve = $("eve");
  eve.max = S.data.latest.eve;
  if (!S.live) { eve.disabled = true; eve.parentElement.classList.add("off"); eve.parentElement.title = "Past dates need the live API, which is not answering right now"; }
  eve.onchange = () => eve.value && loadDate(eve.value);
  $("bg-sat").onclick = () => setBg("sat");
  $("bg-map").onclick = () => setBg("map");
  for (const id of ["about", "ai"]) {
    $(id + "-btn").onclick = () => $(id).showModal();
    $(id + "-close").onclick = () => $(id).close();
  }
  addEventListener("resize", () => S.map.invalidateSize());
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
    S.live = api;
    if (j.eve >= S.data.latest.eve) { S.data.latest = fromApi(j); S.liveLatest = true; }
  } catch (e) { console.warn("Live API unavailable, using the saved forecast", e); }
}

async function loadDate(d) {
  $("status").textContent = "Computing the forecast issued on " + fmt(d, {day: "numeric", month: "long", year: "numeric"}) + "…";
  try {
    const r = await fetch(`${S.live}/forecast/all?eve=${d}`, {signal: AbortSignal.timeout(30000)});
    if (!r.ok) throw new Error((await r.json()).detail || r.status);
    S.data.date = fromApi(await r.json());
    setMode("date");
  } catch (e) { $("status").textContent = "No forecast for that date: " + e.message; }
}

// ---------------------------------------------------------------- map
function initMap(geo) {
  S.map = L.map("map", {zoomSnap: 0.25, minZoom: 7, maxZoom: 12, zoomControl: false});
  L.control.zoom({position: "topright"}).addTo(S.map);
  S.map.attributionControl.setPrefix(false);
  S.sat = L.tileLayer("", {maxNativeZoom: 9, attribution: "NASA GIBS"});
  S.base = L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    {subdomains: "abcd", attribution: "© OpenStreetMap contributors © CARTO"});
  S.sat.addTo(S.map);
  S.layer = L.geoJSON(geo, {
    onEachFeature: (f, l) => {
      l.on("click", () => { S.canton = f.properties.canton_id; render(); });
      l.bindTooltip(f.properties.name, {permanent: true, direction: "center", className: "clabel"});
    }
  }).addTo(S.map);
  S.dots = L.layerGroup().addTo(S.map);
  S.fireTicket = 0;
  S.map.fitBounds(S.layer.getBounds(), {padding: [16, 16]});
}

function setBg(b) {
  S.bg = b;
  $("bg-sat").classList.toggle("on", b === "sat");
  $("bg-map").classList.toggle("on", b === "map");
  if (b === "sat") { S.map.removeLayer(S.base); S.sat.addTo(S.map); } else { S.map.removeLayer(S.sat); S.base.addTo(S.map); }
  S.sat.bringToBack(); S.base.bringToBack();
  $("map").parentElement.classList.toggle("basemap", b === "map");
  render();
}

function satellite(eve) {
  // Newest image that surely exists: the eve, or yesterday (UTC) for today's forecast
  const y = new Date(Date.now() - 864e5).toISOString().slice(0, 10);
  const d = eve < y ? eve : y;
  const viirs = d >= "2018-01-05";
  const layer = viirs ? "VIIRS_NOAA20_CorrectedReflectance_TrueColor" : "MODIS_Terra_CorrectedReflectance_TrueColor";
  const url = `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer}/default/${d}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`;
  if (S.sat._url !== url) S.sat.setUrl(url);
  $("source").textContent = S.bg === "sat"
    ? `Satellite image: NASA GIBS, ${viirs ? "VIIRS NOAA-20" : "MODIS Terra"} true colour, ${fmt(d, {day: "numeric", month: "short", year: "numeric"})} · Boundaries: geoBoundaries`
    : "Map: © OpenStreetMap contributors, © CARTO · Boundaries: geoBoundaries";
}

// Fire detections of the reference satellite (NASA FIRMS) for the selected day
const PTS = {};
const yearPoints = y => PTS[y] ??= fetch(`data/fires/${y}.json`).then(r => r.ok ? r.json() : {days: {}}).then(j => j.days).catch(() => ({}));
async function drawFires(date) {
  const ticket = ++S.fireTicket;
  const past = S.fire && date <= S.fire.through;
  const xy = past ? ((await yearPoints(date.slice(0, 4)))[date.slice(5)] || []) : [];
  if (ticket !== S.fireTicket) return;
  S.dots.clearLayers();
  for (let i = 0; i < xy.length; i += 2)
    L.circleMarker([xy[i], xy[i + 1]], {radius: 4, color: "#FFFFFF", weight: 1.2, fillColor: "#FF3B1F", fillOpacity: 1, interactive: false}).addTo(S.dots);
  const el = $("dotnote"), n = xy.length / 2;
  el.hidden = !past;
  el.innerHTML = `<i></i>${n} fire detection${n === 1 ? "" : "s"} in Guanacaste on ${fmt(date, {day: "numeric", month: "short"})} · NASA FIRMS`;
}

// ---------------------------------------------------------------- state
function setMode(m) {
  S.mode = m;
  S.day = m === "demo" ? 4 : 0;
  if (m === "demo") S.canton = "CR501";
  $("m-latest").classList.toggle("on", m === "latest");
  $("m-demo").classList.toggle("on", m === "demo");
  $("eve").parentElement.classList.toggle("on", m === "date");
  if (m !== "date") $("eve").value = "";
  render();
}

function observed(sel) {
  if (S.fire) for (const d of sel.days) if (d.fire_observed == null && d.date <= S.fire.through)
    d.fire_observed = S.fire.sets[S.canton]?.has(Math.round((Date.parse(d.date + "T00:00:00Z") - S.fire.t0) / 864e5)) ? 1 : 0;
}

// ---------------------------------------------------------------- render
function render() {
  const D = S.data[S.mode], sel = D.cantons[S.canton];
  observed(sel);
  const day = sel.days[S.day];
  const name = S.geo.features.find(f => f.properties.canton_id === S.canton).properties.name;
  $("canton").value = S.canton;
  satellite(D.eve);
  drawFires(day.date);

  // status line
  const inp = D.inputs || {}, eve = fmt(D.eve, {weekday: "short", day: "numeric", month: "short", year: "numeric"});
  const short = d => fmt(d, {day: "numeric", month: "short"});
  $("status").innerHTML = S.mode === "demo"
    ? `<span class="dot"></span><b>Demo week</b> Forecast issued ${eve} by a model trained without any 2018 data, then compared with what the satellites detected.`
    : S.mode === "date"
      ? `<span class="dot live"></span><b>Past date</b> Forecast issued ${eve}, computed just now by the <a href="${S.live}/docs">API</a>. Past dates use the official model (trained on 2012–2025); only the demo week is a strict blind test.`
      : S.liveLatest
        ? `<span class="dot live"></span><b>Live</b> Forecast issued ${eve} by the <a href="${S.live}/docs">API</a>.` +
          (inp.recent_fire_through ? ` Fire data through ${short(inp.recent_fire_through)} · weather from ${short(inp.weather_as_of)} (NASA publishes it a few days late).` : "")
        : `<span class="dot"></span><b>Saved forecast</b> Issued ${eve}; refreshed every morning.`;

  // map
  $("mapday").textContent = fmt(day.date, {weekday: "long", day: "numeric", month: "long", year: "numeric"});
  S.layer.eachLayer(l => {
    const id = l.feature.properties.canton_id, c = D.cantons[id], on = id === S.canton;
    l.setStyle({fillColor: c ? LV[c.days[S.day].level] : "#999", fillOpacity: on ? 0.5 : 0.32,
                color: S.bg === "sat" ? "#FFFFFF" : "#5B6675", weight: on ? 3 : 1, opacity: on ? 1 : 0.8});
    l.getTooltip().getElement()?.classList.toggle("sel", on);
    if (on) l.bringToFront();
  });

  // risk card
  $("riskplace").textContent = name;
  $("riskdate").textContent = fmt(day.date, {weekday: "short", day: "numeric", month: "short", year: "numeric"});
  $("riskidx").textContent = idx(day.prob);
  $("risklvl").innerHTML = `<i style="background:${LV[day.level]}"></i>${day.level}`;
  const obs = $("obs");
  obs.hidden = day.fire_observed == null;
  obs.className = "obs" + (day.fire_observed ? " yes" : "");
  obs.innerHTML = day.fire_observed ? `${icon("check")} Fire detected by satellite` : "No fire detected by satellite";
  $("risktext").innerHTML = `Chance that satellites detect a vegetation fire in ${name} that day: <b>${pct(day.prob)}</b>. A normal year at this time: ${pct(day.normal_prob)}.`;

  // outlook
  $("issued").textContent = "issued " + fmt(D.eve, {day: "numeric", month: "short"});
  $("outlook").innerHTML = sel.days.map((d, i) => `
    <button class="day${i === S.day ? " sel" : ""}" data-i="${i}" aria-pressed="${i === S.day}" title="${d.level}">
      <span class="d1">${fmt(d.date, {weekday: "short"})}</span><span class="d2">${fmt(d.date, {day: "numeric", month: "short"})}</span>
      ${flameFor(d.level)}<span class="v">${idx(d.prob)}</span>
      <span class="o${d.fire_observed ? " yes" : ""}">${d.fire_observed == null ? "" : d.fire_observed ? "fire" : "–"}</span>
    </button>`).join("");
  document.querySelectorAll(".day").forEach(b => b.onclick = () => { S.day = +b.dataset.i; render(); });

  // conditions and vegetation
  const c = sel.conditions, v = (x, u = "") => x == null ? "–" : x + u;
  const facts = a => a.map(([ic, k, val]) => `<div class="fact">${icon(ic)}<div><small>${k}</small><b>${val}</b></div></div>`).join("");
  $("cdate").textContent = "NASA POWER · " + fmt(c.date || D.eve, {day: "numeric", month: "short"});
  $("conds").innerHTML = facts([["temp", "Max / min", `${v(c.t_max_c)}° / ${v(c.t_min_c)}°`], ["drop", "Humidity", v(c.humidity_pct, " %")],
    ["wind", "Wind", v(c.wind_kmh, " km/h")], ["rain", "Rain 24 h", v(c.rain_mm, " mm")]]);
  $("inds").innerHTML = facts([["leaf", "NDVI · greenness", v(c.ndvi)], ["drop", "NDMI · leaf moisture", v(c.ndmi)],
    ["sun", "Days without rain", v(c.days_without_rain)]]);

  // why
  $("hist").innerHTML = `A normal year on this date: <b>${pct(day.normal_prob)}</b>. With this year’s conditions: <b>${pct(day.prob)}</b>.`;
  $("drivers").innerHTML = [["Weather", day.x_weather], ["Vegetation", day.x_vegetation], ["Recent fire", day.x_recent_fire]].map(([n, x]) => {
    const w = Math.min(Math.abs(Math.log2(x)), 1) * 50, up = x >= 1;
    return `<div class="drv"><span>${n}</span><div class="bar"><div class="mid"></div>
      <div class="fill" style="${up ? "left:50%" : `left:${50 - w}%`};width:${w}%;background:${up ? "#E7862E" : "#3E9E6A"}"></div></div><b>×${x.toFixed(2)}</b></div>`;
  }).join("");
}

function renderAbout() {
  const m = S.meta.metrics;
  $("metrics").innerHTML = [["+" + (m.bss_2013_2025 * 100).toFixed(1) + " %", "more accurate than an average year"],
    [m.years_bss_positive, "seasons better than the average year"],
    [m.auc_model_2013_2025.toFixed(3), "AUC (average year: " + m.auc_ref_2013_2025.toFixed(3) + ")"],
    ["+" + (m.lead_bss["5"] * 100).toFixed(1) + " %", "still better on day 5"]].map(([b, s]) => `<div class="stat"><b>${b}</b><small>${s}</small></div>`).join("");
  const leg = S.meta.levels.map(([up, n], i, a) =>
    `<span><i style="background:${LV[n]}"></i>${n} ${i ? Math.round(a[i - 1][0] * 100) : 0}${up > 1 ? "+ %" : "–" + Math.round(up * 100) + " %"}</span>`).join("");
  $("legend").innerHTML = leg; $("legend2").innerHTML = leg;
  $("runid").textContent = S.meta.run_id;
  $("apilink").href = (window.VIGIA_API || "").replace(/\/$/, "") + "/docs";
}

load();
