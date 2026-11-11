const numberFormat = new Intl.NumberFormat("en-IN");
const decimalFormat = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 3,
  maximumFractionDigits: 4,
});

const colorGradients = {
  "RdYlGn": "linear-gradient(90deg, #a50026, #f46d43, #ffffbf, #a6d96a, #006837)",
  "BrBG": "linear-gradient(90deg, #543005, #bf812d, #f5f5f5, #80cdc1, #003c30)",
  "YlOrRd": "linear-gradient(90deg, #ffffcc, #fed976, #fd8d3c, #e31a1c, #800026)",
};

let dashboardData;
let activeIndex;

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function formatNumber(value) {
  return numberFormat.format(value);
}

function formatDecimal(value) {
  return decimalFormat.format(value);
}

function showError(message) {
  const error = document.getElementById("app-error");
  error.textContent = message;
  error.hidden = false;
  document.getElementById("loading-state").hidden = true;
  document.getElementById("dashboard").hidden = true;
}

function renderStatistics(indices) {
  const body = document.getElementById("statistics-body");
  body.replaceChildren();

  for (const index of indices) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    nameCell.className = "table-index";
    nameCell.textContent = index.name;
    row.append(nameCell);

    const stat = index.statistics;
    for (const value of [
      formatDecimal(stat.minimum),
      formatDecimal(stat.maximum),
      formatDecimal(stat.mean),
      formatDecimal(stat.median),
      formatDecimal(stat.standard_deviation),
      formatNumber(stat.valid_pixels),
      formatNumber(stat.invalid_pixels),
    ]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    body.append(row);
  }
}

function renderIndexTabs(indices) {
  const tabs = document.getElementById("index-tabs");
  tabs.replaceChildren();

  for (const index of indices) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "index-tab";
    button.role = "tab";
    button.textContent = index.name;
    button.setAttribute("aria-selected", "false");
    button.addEventListener("click", () => selectIndex(index.name));
    tabs.append(button);
  }
}

function renderBands(bands) {
  const list = document.getElementById("band-list");
  list.replaceChildren();
  for (const band of bands) {
    const item = document.createElement("div");
    item.className = "band-item";
    const code = document.createElement("span");
    code.className = "band-code";
    code.textContent = band.name;
    const label = document.createElement("span");
    label.textContent = band.label;
    item.append(code, label);
    list.append(item);
  }
}

function selectIndex(indexName) {
  const index = dashboardData.indices.find((candidate) => candidate.name === indexName);
  if (!index) return;
  activeIndex = index.name;
  const stat = index.statistics;
  const tabs = document.querySelectorAll(".index-tab");
  for (const tab of tabs) {
    const selected = tab.textContent === indexName;
    tab.classList.toggle("selected", selected);
    tab.setAttribute("aria-selected", String(selected));
  }

  setText("map-title", `${index.name} · ${index.meaning}`);
  setText("legend-index", index.name);
  setText("profile-name", index.name);
  setText("profile-chip", index.name);
  setText("profile-formula", index.formula);
  setText("profile-meaning", index.meaning);
  setText("profile-use", index.use);
  setText("index-mean", formatDecimal(stat.mean));
  setText("index-median", formatDecimal(stat.median));
  setText("index-min", formatDecimal(stat.minimum));
  setText("index-max", formatDecimal(stat.maximum));
  setText("index-std", formatDecimal(stat.standard_deviation));
  setText("index-valid", formatNumber(stat.valid_pixels));
  setText("display-min", formatDecimal(stat.display_min));
  setText("display-max", formatDecimal(stat.display_max));
  document.getElementById("legend-gradient").style.background =
    colorGradients[index.cmap] || colorGradients["RdYlGn"];

  const image = document.getElementById("index-map");
  image.src = `${index.preview_url}?v=${encodeURIComponent(indexName)}`;
  image.dataset.index = indexName;
  document.getElementById("download-selected").href = index.download_url;
  document.getElementById("pixel-result").innerHTML =
    '<span class="pixel-pin">⌖</span><span>Click any map pixel to inspect its index value and map coordinates.</span>';
}

function renderDashboard(data) {
  dashboardData = data;
  const metadata = data.metadata;
  setText("study-area", metadata.study_area);
  setText("acquisition-date", metadata.acquisition_date);
  setText("collection", `Sentinel-2 · ${metadata.collection}`);
  setText("resolution", `${metadata.resolution_m} m`);
  setText("crs", metadata.crs);
  setText("valid-pixels", formatNumber(metadata.valid_pixels));
  setText("invalid-pixels", formatNumber(metadata.invalid_pixels));
  setText(
    "valid-percent",
    `${((100 * metadata.valid_pixels) / metadata.total_pixels).toFixed(1)}%`,
  );
  setText(
    "invalid-percent",
    `${((100 * metadata.invalid_pixels) / metadata.total_pixels).toFixed(1)}%`,
  );
  setText("dimensions", `${metadata.width} × ${metadata.height}`);
  setText("input-name", metadata.input_name);
  document.getElementById("combined-map").src = data.visualization_url;

  renderIndexTabs(data.indices);
  renderStatistics(data.indices);
  renderBands(data.bands);
  selectIndex("NDVI");
  document.getElementById("loading-state").hidden = true;
  document.getElementById("app-error").hidden = true;
  document.getElementById("dashboard").hidden = false;
}

async function loadDashboard() {
  const button = document.getElementById("refresh-button");
  button.classList.add("spinning");
  document.getElementById("loading-state").hidden = false;
  document.getElementById("dashboard").hidden = true;
  document.getElementById("app-error").hidden = true;

  try {
    const response = await fetch("/api/dashboard", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to load scene products.");
    renderDashboard(data);
  } catch (error) {
    showError(error.message);
  } finally {
    button.classList.remove("spinning");
  }
}

async function inspectPixel(event) {
  const image = event.currentTarget;
  const bounds = image.getBoundingClientRect();
  const column = Math.floor(((event.clientX - bounds.left) / bounds.width) * image.naturalWidth);
  const row = Math.floor(((event.clientY - bounds.top) / bounds.height) * image.naturalHeight);
  const indexName = image.dataset.index;
  const result = document.getElementById("pixel-result");

  result.innerHTML = '<span class="pixel-pin">⌖</span><span>Reading selected pixel…</span>';
  try {
    const response = await fetch(
      `/api/indices/${encodeURIComponent(indexName)}/pixel?row=${row}&column=${column}`,
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to read this pixel.");

    const message = data.valid
      ? `<strong>${indexName} ${formatDecimal(data.value)}</strong> &nbsp;·&nbsp; Row ${data.row}, column ${data.column} &nbsp;·&nbsp; ${formatDecimal(data.easting)} E, ${formatDecimal(data.northing)} N`
      : `<strong>Masked pixel</strong> &nbsp;·&nbsp; Row ${data.row}, column ${data.column} &nbsp;·&nbsp; ${formatDecimal(data.easting)} E, ${formatDecimal(data.northing)} N`;
    result.innerHTML = `<span class="pixel-pin">⌖</span><span>${message}</span>`;
  } catch (error) {
    result.innerHTML = `<span class="pixel-pin">!</span><span>${error.message}</span>`;
  }
}

document.getElementById("refresh-button").addEventListener("click", loadDashboard);
document.getElementById("index-map").addEventListener("click", inspectPixel);
loadDashboard();
