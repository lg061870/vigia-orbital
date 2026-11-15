// Vigía Orbital website. Forecasts come from the live API (FastAPI) when it answers,
// otherwise from the saved files in site/data/ (rebuilt every morning by the Pages workflow).
const LV = {
  "Low": {c: "#2E9E6A", in: "#BFE8D2", s: 0.55, t: "#0F2236"},
  "Moderate": {c: "#E8C547", in: "#FFF1B8", s: 0.75, t: "#0F2236"},
  "High": {c: "#F08A24", in: "#FFD27A", s: 1.0, t: "#0F2236"},
  "Very high": {c: "#D2382C", in: "#F7B0A8", s: 1.1, t: "#FFFFFF"},
  "Extreme": {c: "#7E1B1B", in: "#E08A8A", s: 1.2, t: "#FFFFFF"},
};
const S = {mode: "latest", canton: "CR501", day: 0, data: {}, meta: null, layer: null, sat: null, map: null, live: null};
const $ = id => document.getElementById(id);
const fmt = (iso, o) => new Date(iso + "T00:00:00Z").toLocaleDateString("en-GB", {timeZone: "UTC", ...o});
const idx = p => (Math.round(p * 100 + 1e-9) / 100).toFixed(2);
const pct = p => (p < 0.01 ? "<1" : Math.round(p * 100)) + " %";
const flame = (lvl, h) => {
  const L = LV[lvl], w = Math.round(h * 56 / 72);
  return `<svg width="${w * L.s}" height="${h * L.s}" viewBox="8 0 40 62" aria-label="${lvl} risk"><path d="M28 0c4 14 20 22 20 42a20 20 0 0 1-40 0c0-10 6-16 10-22 2 8 6 12 10 12C28 22 22 12 28 0z" fill="${L.c}"/><path d="M28 34c3 6 10 9 10 18a10 10 0 0 1-20 0c0-5 4-9 6-12 1 3 2 5 4 5 0-4-2-7 0-11z" fill="${L.in}"/></svg>`;
};
const pill = (lvl, cls) => `<span class="${cls}" style="background:${LV[lvl].c};color:${LV[lvl].t}">${lvl}</span>`;

async function load() {
  const get = f => fetch("data/" + f).then(r => r.json());
  const [geo, latest, demo, meta] = await Promise.all([get("cantons.geojson"), get("latest.json"), get("demo.json"), get("meta.json")]);
  S.data = {latest, demo}; S.meta = meta; S.geo = geo;
  await tryLiveApi();
  initMap(geo);
  const sel = $("canton");
  sel.innerHTML = geo.features.map(f => f.properties).sort((a, b) => a.name.localeCompare(b.name))
    .map(p => `<option value="${p.canton_id}">${p.name} (Guanacaste)</option>`).join("");
  sel.onchange = () => { S.canton = sel.value; render(); };
  $("m-latest").onclick = () => setMode("latest");
  $("m-demo").onclick = () => setMode("demo");
  const eve = $("eve");
  eve.max = S.data.latest.eve;
  if (!S.live) { eve.disabled = true; eve.parentElement.classList.add("off"); eve.parentElement.title = "Needs the live API, which is not answering right now"; }
  eve.onchange = () => eve.value && loadDate(eve.value);
  renderLegend(); renderMetrics();
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
    S.live = api;                                    // the API answers: past dates are available
    if (j.eve >= S.data.latest.eve) { S.data.latest = fromApi(j); S.liveLatest = true; }
  } catch (e) { console.warn("Live API unavailable, using the saved forecast", e); }
}

async function loadDate(d) {
  $("note").textContent = "Asking the API for the forecast issued on " + fmt(d, {day: "numeric", month: "long", year: "numeric"}) + "…";
  try {
    const r = await fetch(`${S.live}/forecast/all?eve=${d}`, {signal: AbortSignal.timeout(30000)});
    if (!r.ok) throw new Error((await r.json()).detail || r.status);
    S.data.date = fromApi(await r.json());
    setMode("date");
  } catch (e) { $("note").textContent = "No forecast for that date: " + e.message; }
}

function initMap(geo) {
  S.map = L.map("map", {zoomSnap: 0.25, minZoom: 7, maxZoom: 11});
  S.sat = L.tileLayer("", {maxNativeZoom: 9, attribution: "Image: NASA GIBS · boundaries: geoBoundaries"}).addTo(S.map);
  S.layer = L.geoJSON(geo, {
    onEachFeature: (f, l) => {
      l.on("click", () => { S.canton = f.properties.canton_id; render(); });
      l.bindTooltip(f.properties.name, {permanent: true, direction: "center", className: "clabel"});
    }
  }).addTo(S.map);
  S.map.fitBounds(S.layer.getBounds(), {padding: [8, 8]});
}

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

function satellite(eve) {
  // Newest image that surely exists: the eve, or yesterday (UTC) for today's forecast
  const y = new Date(Date.now() - 864e5).toISOString().slice(0, 10);
  const d = eve < y ? eve : y;
  const url = `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/${d}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`;
  if (S.sat._url !== url) S.sat.setUrl(url);
  return d;
}

function render() {
  const D = S.data[S.mode], sel = D.cantons[S.canton], day = sel.days[S.day];
  const name = S.geo.features.find(f => f.properties.canton_id === S.canton).properties.name;
  $("canton").value = S.canton;
  const imgDate = satellite(D.eve);
  $("issued").textContent = "Issued on the evening of " + fmt(D.eve, {weekday: "long", day: "numeric", month: "long", year: "numeric"});
  const inp = D.inputs || {};
  $("note").innerHTML = S.mode === "demo"
    ? "A real past week, forecast by a model trained <b>without any 2018 data</b>. The badges show what the satellites detected afterwards."
    : S.mode === "date"
      ? `Computed just now by the <a href="${S.live}/docs">API</a> with the data known that evening. Past dates use the official model (trained on 2012–2025), so only the Demo week is a strict blind test.`
      : S.liveLatest
        ? `<b>Live:</b> computed just now by the <a href="${S.live}/docs">API</a>.` + (inp.recent_fire_through
          ? ` Fire detections through ${fmt(inp.recent_fire_through, {day: "numeric", month: "short"})}; weather from ${fmt(inp.weather_as_of, {day: "numeric", month: "short"})} (NASA publishes it a few days late).` : "")
        : `Saved forecast, refreshed every morning` + (inp.weather_as_of ? ` (weather from ${fmt(inp.weather_as_of, {day: "numeric", month: "short"})})` : "") + ".";

  S.layer.eachLayer(l => {
    const id = l.feature.properties.canton_id, c = D.cantons[id], on = id === S.canton;
    l.setStyle({fillColor: c ? LV[c.days[S.day].level].c : "#999", fillOpacity: on ? 0.6 : 0.42,
                color: on ? "#FFFFFF" : "#0F2236", weight: on ? 4 : 1.5});
    l.getTooltip().getElement()?.classList.toggle("sel", on);
    if (on) l.bringToFront();
  });

  $("datebar").textContent = `${name} · ${fmt(day.date, {weekday: "long", day: "numeric", month: "long", year: "numeric"})}`;
  $("bigflame").innerHTML = flame(day.level, 46);
  $("riskpill").outerHTML = pill(day.level, "risk-pill").replace("<span", '<span id="riskpill"');
  $("riskidx").textContent = `Index: ${idx(day.prob)}`;
  const obs = $("obs"), seen = day.fire_observed;
  obs.hidden = seen == null;
  obs.className = "obs" + (seen ? "" : " none");
  obs.textContent = seen ? "✓ Fire detected" : "No fire detected";

  const c = sel.conditions, v = (x, u = "") => x == null ? "–" : x + u;
  $("cdate").textContent = "· NASA POWER, " + fmt(c.date || D.eve, {day: "numeric", month: "short"});
  $("conds").innerHTML = [[`${v(c.t_max_c)}/${v(c.t_min_c)}°`, "Max / min °C"], [v(c.humidity_pct, " %"), "Humidity"],
    [v(c.wind_kmh), "Wind km/h"], [v(c.rain_mm, " mm"), "Rain 24 h"]].map(([b, s]) => `<div class="cond"><b>${b}</b><small>${s}</small></div>`).join("");
  $("inds").innerHTML = [[v(c.ndvi), "NDVI · greenness"], [v(c.ndmi), "NDMI · leaf moisture"], [v(c.days_without_rain), "Days without rain"],
    [fmt(imgDate, {day: "numeric", month: "short"}), "Satellite image"]].map(([b, s]) => `<div class="cond"><b>${b}</b><small>${s}</small></div>`).join("");

  $("hist").innerHTML = `A normal year on this date: <b>${pct(day.normal_prob)}</b>. With this year’s conditions: <b>${pct(day.prob)}</b>.`;
  $("drivers").innerHTML = [["Weather", day.x_weather], ["Vegetation", day.x_vegetation], ["Recent fire", day.x_recent_fire]]
    .map(([n, x]) => `<div class="drv"><b class="${x > 1.02 ? "up" : x < 0.98 ? "down" : "flat"}">×${x.toFixed(2)}</b><small>${n}</small></div>`).join("");

  $("striplabel").innerHTML = `${name}<br>5-day forecast`;
  $("cards").innerHTML = sel.days.map((d, i) => `
    <button class="card${i === S.day ? " sel" : ""}" data-i="${i}" aria-pressed="${i === S.day}">
      <span class="dow">${fmt(d.date, {weekday: "short"})}</span><span class="date">${fmt(d.date, {day: "numeric", month: "short"})}</span>
      <span class="flame">${flame(d.level, 56)}</span>
      ${pill(d.level, "lvl")}<span class="idx">Index: ${idx(d.prob)}</span>
      ${d.fire_observed == null ? "" : `<span class="seen${d.fire_observed ? "" : " none"}">${d.fire_observed ? "✓ fire detected" : "no fire"}</span>`}
    </button>`).join("");
  document.querySelectorAll(".card").forEach(b => b.onclick = () => { S.day = +b.dataset.i; render(); });
}

function renderLegend() {
  $("legend").innerHTML = S.meta.levels.map(([u, n], i, a) =>
    `<span><i style="background:${LV[n].c}"></i>${n} ${i ? Math.round(a[i - 1][0] * 100) : 0}${u > 1 ? " % +" : "–" + Math.round(u * 100) + " %"}</span>`).join("");
}

function renderMetrics() {
  const m = S.meta.metrics;
  $("metrics").innerHTML = [["+" + (m.bss_2013_2025 * 100).toFixed(1) + " %", "more accurate than an average year"],
    [m.years_bss_positive, "seasons better than the average year"],
    [m.auc_model_2013_2025.toFixed(3), "AUC (average year: " + m.auc_ref_2013_2025.toFixed(3) + ")"],
    ["+" + (m.lead_bss["5"] * 100).toFixed(1) + " %", "still better on day 5"]].map(([b, s]) => `<div class="stat"><b>${b}</b><small>${s}</small></div>`).join("");
  $("runid").textContent = S.meta.run_id;
  $("apilink").href = (window.VIGIA_API || "").replace(/\/$/, "") + "/docs";
}

load();
