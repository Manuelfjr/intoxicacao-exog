const SEXES = ["Feminino", "Masculino"];

const STATE_LABELS = {
  Acre: "Acre",
  "Distrito Federal": "Distrito Federal",
  "Sao Paulo": "São Paulo",
  Paraiba: "Paraíba",
  "Santa Catarina": "Santa Catarina",
};

const TOXIC_GROUP_LABELS = {
  "Cosmético_higiene pessoal": "Cosmético e higiene pessoal",
  "Agrotóxico uso agrícola": "Agrotóxico agrícola",
  "Agrotóxico uso doméstico": "Agrotóxico doméstico",
  "Agrotóxico uso saúde pública": "Agrotóxico saúde pública",
  "Prod. uso domiciliar": "Produto domiciliar",
  "Prod. químico uso industrial": "Químico industrial",
  "Prod. uso veterinário": "Produto veterinário",
  "Ign/Branco": "Ignorado ou em branco",
};

const TOXIC_TOP_N = 8;
// Aspas simples: o nome da fonte vai para atributos style do SVG exportado.
const FONT_BODY = "'Source Sans 3', 'Trebuchet MS', sans-serif";
const FONT_DISPLAY = "'Sora', 'Trebuchet MS', sans-serif";
const THEME_STORAGE_KEY = "tox-older-theme";

const CHART_CONFIG = {
  displayModeBar: false,
  responsive: true,
};

let dashboardData = null;
let selectedSex = "Todos";
let selectedStates = [];
let heatmapMode = "relative";
let toxicMode = "count";
let theme = {};

document.addEventListener("DOMContentLoaded", async () => {
  try {
    applyStoredTheme();
    initBackground();
    dashboardData = await fetchDashboardData();
    selectedStates = [...dashboardData.metadata.states];

    hydrateMetadata();
    buildSexFilter();
    buildStateFilter();
    buildModeControl("heatmap-mode", [
      ["relative", "Relativo ao pico"],
      ["absolute", "Casos absolutos"],
    ], () => heatmapMode, (value) => {
      heatmapMode = value;
      renderHeatmap(getFilteredYearTotals());
    });
    buildModeControl("toxic-mode", [
      ["count", "Casos"],
      ["share", "% por sexo"],
    ], () => toxicMode, (value) => {
      toxicMode = value;
      renderToxicChart(getFilteredTidyCounts());
    });
    bindToolbarActions();
    bindResize();
    renderAll();
  } catch (error) {
    console.error(error);
    document.body.innerHTML = `
      <main style="padding: 32px; font-family: 'Source Sans 3', 'Trebuchet MS', sans-serif; color: #16313A;">
        <h1>Falha ao carregar o dashboard</h1>
        <p>Não foi possível inicializar os dados da interface.</p>
        <pre style="white-space: pre-wrap; background: #F5F8F9; padding: 16px; border-radius: 12px;">${String(error.message || error)}</pre>
      </main>
    `;
  }
});

async function fetchDashboardData() {
  if (window.__DASHBOARD_DATA__) {
    return window.__DASHBOARD_DATA__;
  }

  const response = await fetch("./data/dashboard_data.json");
  if (!response.ok) {
    throw new Error("Não foi possível carregar os dados do dashboard.");
  }
  return response.json();
}

/* ---------- Theme ---------- */

function applyStoredTheme() {
  let stored = null;
  try {
    stored = localStorage.getItem(THEME_STORAGE_KEY);
  } catch (error) {
    stored = null;
  }
  document.documentElement.dataset.theme = stored === "dark" ? "dark" : "light";
  readTheme();

  document.getElementById("theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch (error) {
      // Preferência apenas local; segue sem persistir.
    }
    readTheme();
    window.dispatchEvent(new Event("resize"));
    if (dashboardData) {
      renderAll();
    }
  });
}

function readTheme() {
  const styles = getComputedStyle(document.documentElement);
  const token = (name) => styles.getPropertyValue(name).trim();
  theme = {
    text: token("--text"),
    muted: token("--muted"),
    faint: token("--faint"),
    grid: token("--grid"),
    axis: token("--axis"),
    accent: token("--accent"),
    panel: token("--panel-solid"),
    border: token("--border-strong"),
    sex: { Feminino: token("--female"), Masculino: token("--male") },
    heat: [0, 1, 2, 3, 4, 5, 6].map((step) => token(`--heat-${step}`)),
    dot: token("--dot"),
    scale: parseFloat(styles.fontSize) / 16,
  };
}

function fs(value) {
  return Math.round(value * theme.scale * 10) / 10;
}

function baseLayout(overrides = {}) {
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: { t: 24, r: 16, b: 40, l: 52 },
    font: { family: FONT_BODY, color: theme.text, size: fs(13) },
    hoverlabel: {
      bgcolor: theme.panel,
      bordercolor: theme.border,
      font: { family: FONT_BODY, color: theme.text, size: fs(13) },
    },
    showlegend: false,
    ...overrides,
  };
}

function axis(overrides = {}) {
  return {
    gridcolor: theme.grid,
    zerolinecolor: theme.axis,
    linecolor: theme.axis,
    tickcolor: theme.axis,
    tickfont: { color: theme.muted, size: fs(12) },
    title: { font: { color: theme.muted, size: fs(12) } },
    automargin: true,
    ...overrides,
  };
}

function yearAxis(overrides = {}) {
  return axis({
    showgrid: false,
    showline: true,
    ticks: "outside",
    ticklen: 4,
    dtick: 2,
    tick0: 2007,
    fixedrange: true,
    ...overrides,
  });
}

function hexToRgba(hex, alpha) {
  const value = hex.replace("#", "");
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/* ---------- Filters ---------- */

function hydrateMetadata() {
  const { start_year: startYear, end_year: endYear, generated_at_utc: generatedAt, states } = dashboardData.metadata;
  document.getElementById("meta-period").textContent = `${startYear} – ${endYear}`;
  document.getElementById("meta-states").textContent = `${states.length} estados`;
  document.getElementById("meta-generated").textContent = `Atualizado em ${formatDateTime(generatedAt)}`;
}

function buildSexFilter() {
  const container = document.getElementById("sex-filter");
  container.innerHTML = "";

  ["Todos", ...SEXES].forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `segmented-button${option === selectedSex ? " is-active" : ""}`;
    button.setAttribute("aria-pressed", String(option === selectedSex));
    if (option !== "Todos") {
      const swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = theme.sex[option];
      button.appendChild(swatch);
    }
    button.appendChild(document.createTextNode(option));
    button.addEventListener("click", () => {
      selectedSex = option;
      buildSexFilter();
      renderDashboard();
    });
    container.appendChild(button);
  });
}

function buildStateFilter() {
  const container = document.getElementById("state-filter");
  const states = sortStatesByTotal(dashboardData.metadata.states);
  const allSelected = selectedStates.length === states.length;

  container.innerHTML = "";

  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.className = `chip${allSelected ? " is-active" : ""}`;
  allButton.textContent = "Todos";
  allButton.setAttribute("aria-pressed", String(allSelected));
  allButton.title = "Selecionar todos os estados";
  allButton.addEventListener("click", () => {
    selectedStates = [...dashboardData.metadata.states];
    buildStateFilter();
    renderDashboard();
  });
  container.appendChild(allButton);

  states.forEach((state) => {
    const isActive = !allSelected && selectedStates.includes(state);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `chip${isActive ? " is-active" : ""}`;
    button.textContent = formatStateLabel(state);
    button.setAttribute("aria-pressed", String(isActive));
    button.title = "Clique para incluir ou remover este estado do recorte";
    button.addEventListener("click", () => toggleStateSelection(state));
    container.appendChild(button);
  });
}

function buildModeControl(containerId, options, getValue, onChange) {
  const container = document.getElementById(containerId);
  const draw = () => {
    container.innerHTML = "";
    options.forEach(([value, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `segmented-button${getValue() === value ? " is-active" : ""}`;
      button.setAttribute("aria-pressed", String(getValue() === value));
      button.textContent = label;
      button.addEventListener("click", () => {
        onChange(value);
        draw();
      });
      container.appendChild(button);
    });
  };
  draw();
}

function bindToolbarActions() {
  document.getElementById("reset-filters").addEventListener("click", () => {
    selectedSex = "Todos";
    selectedStates = [...dashboardData.metadata.states];
    buildSexFilter();
    buildStateFilter();
    renderDashboard();
  });
}

function bindResize() {
  let timer = null;
  let lastWidth = window.innerWidth;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (Math.abs(window.innerWidth - lastWidth) < 24) {
        return;
      }
      lastWidth = window.innerWidth;
      readTheme();
      renderDashboard();
    }, 180);
  });
}

function toggleStateSelection(state) {
  const allStates = dashboardData.metadata.states;

  if (selectedStates.length === allStates.length) {
    // Com todos ativos, o primeiro clique isola o estado escolhido.
    selectedStates = [state];
  } else if (selectedStates.includes(state)) {
    selectedStates = selectedStates.filter((item) => item !== state);
  } else {
    selectedStates = [...selectedStates, state];
  }

  if (!selectedStates.length) {
    selectedStates = [...allStates];
  }

  buildStateFilter();
  renderDashboard();
}

/* ---------- Data helpers ---------- */

function getFilteredYearTotals() {
  return dashboardData.tables.year_totals.filter((row) => {
    const stateMatch = selectedStates.includes(row.state);
    const sexMatch = selectedSex === "Todos" || row.sex_label === selectedSex;
    return stateMatch && sexMatch;
  });
}

function getStateScopedYearTotals() {
  return dashboardData.tables.year_totals.filter((row) => selectedStates.includes(row.state));
}

function getFilteredTidyCounts() {
  return dashboardData.tables.tidy_counts.filter((row) => {
    const stateMatch = selectedStates.includes(row.state);
    const sexMatch = selectedSex === "Todos" || row.sex_label === selectedSex;
    return stateMatch && sexMatch;
  });
}

function activeSexes() {
  return selectedSex === "Todos" ? SEXES : [selectedSex];
}

function years() {
  return dashboardData.metadata.years;
}

function seriesByYear(rows) {
  const totals = aggregateByYear(rows);
  return years().map((year) => totals.get(year) || 0);
}

function totalsByState(rows) {
  return Object.entries(groupBy(rows, "state"))
    .map(([state, stateRows]) => ({ state, total: sum(stateRows.map((row) => row.total_year)) }))
    .sort((left, right) => right.total - left.total);
}

function sortStatesByTotal(states) {
  const totals = new Map(totalsByState(dashboardData.tables.year_totals).map((item) => [item.state, item.total]));
  return [...states].sort((left, right) => (totals.get(right) || 0) - (totals.get(left) || 0));
}

/* ---------- Render ---------- */

function renderAll() {
  buildSexFilter();
  renderHero();
  renderDashboard();
}

function renderDashboard() {
  const filteredYearTotals = getFilteredYearTotals();
  const stateScopedYearTotals = getStateScopedYearTotals();
  const filteredTidyCounts = getFilteredTidyCounts();

  renderFilterSummary(filteredYearTotals);
  renderMetrics(filteredYearTotals, stateScopedYearTotals);
  renderTrendChart(filteredYearTotals);
  renderShareChart(stateScopedYearTotals);
  renderHeatmap(filteredYearTotals);
  renderMultiples(filteredYearTotals);
  renderStatesChart(stateScopedYearTotals);
  renderToxicChart(filteredTidyCounts);
  renderStateTable(stateScopedYearTotals);
  renderInsights(filteredYearTotals, stateScopedYearTotals, filteredTidyCounts);
}

function renderHero() {
  const allRows = dashboardData.tables.year_totals;
  const total = sum(allRows.map((row) => row.total_year));
  const female = sum(allRows.filter((row) => row.sex_label === "Feminino").map((row) => row.total_year));
  const series = seriesByYear(allRows);

  const agents = Object.entries(groupBy(dashboardData.tables.toxic_profile, "toxic_group"))
    .map(([group, rows]) => ({ group, total: sum(rows.map((row) => row.count)) }))
    .sort((left, right) => right.total - left.total);

  document.getElementById("hero-total").textContent = formatInteger(total);
  document.getElementById("hero-female").textContent = formatPercent((female / total) * 100);
  document.getElementById("hero-agent").textContent = formatToxicGroupLabel(agents[0].group);

  // Sinal: média dos últimos 5 anos contra os 5 anos anteriores.
  const recent = sum(series.slice(-5)) / 5;
  const before = sum(series.slice(-10, -5)) / 5;
  const change = before > 0 ? ((recent - before) / before) * 100 : 0;
  const label = change > 10 ? "Tendência de alta" : change < -10 ? "Tendência de queda" : "Ritmo estável";
  document.getElementById("hero-signal").textContent = label;
  document.getElementById("hero-signal-note").textContent =
    `${change >= 0 ? "+" : "−"}${formatPercent(Math.abs(change))} na média anual dos últimos 5 anos`;
  drawSpark(document.getElementById("hero-signal-spark"), series);
}

function drawSpark(svg, values) {
  const width = 120;
  const height = 36;
  const pad = 4;
  const maxValue = Math.max(...values, 1);
  const points = values.map((value, index) => [
    pad + (index / (values.length - 1)) * (width - pad * 2),
    height - pad - (value / maxValue) * (height - pad * 2),
  ]);
  const line = points.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  const [lastX] = points[points.length - 1];
  const color = theme.accent;
  svg.innerHTML = `
    <path d="${line}L${lastX.toFixed(1)} ${height}L${pad} ${height}Z" fill="${hexToRgba(color, 0.12)}" />
    <path d="${line}" fill="none" stroke="${color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
  `;
}

function renderFilterSummary(rows) {
  const totalStates = dashboardData.metadata.states.length;
  const stateLabel =
    selectedStates.length === totalStates
      ? "todos os estados"
      : formatStateList(selectedStates).join(", ");
  const sexLabel = selectedSex === "Todos" ? "ambos os sexos" : selectedSex.toLowerCase();
  const totalCases = sum(rows.map((row) => row.total_year));

  document.getElementById("filter-summary-text").innerHTML =
    `<strong>${formatInteger(totalCases)} casos</strong> · ${stateLabel} · ${sexLabel}`;
}

function renderMetrics(rows, stateRows) {
  const totalCases = sum(rows.map((row) => row.total_year));
  const series = seriesByYear(rows);
  const latestYear = years()[years().length - 1];
  const latest = series[series.length - 1];
  const previous = series[series.length - 2];
  const dominant = totalsByState(rows)[0];

  setMetric(
    "metric-total",
    formatInteger(totalCases),
    "metric-total-note",
    `${selectedStates.length} estado(s), ${years()[0]}–${latestYear}`
  );

  document.getElementById("metric-latest-label").textContent = `Casos em ${latestYear}`;
  document.getElementById("metric-latest").textContent = formatInteger(latest);
  const latestNote = document.getElementById("metric-latest-note");
  if (previous > 0) {
    const change = ((latest - previous) / previous) * 100;
    const direction = change >= 0 ? "up" : "down";
    const sign = change >= 0 ? "+" : "−";
    latestNote.innerHTML = `<span class="delta delta--${direction}">${sign}${formatPercent(Math.abs(change))}</span> em relação a ${latestYear - 1}`;
  } else {
    latestNote.textContent = `sem casos em ${latestYear - 1} para comparar`;
  }

  const scopeTotal = sum(stateRows.map((row) => row.total_year));
  if (selectedSex === "Todos") {
    const female = sum(rows.filter((row) => row.sex_label === "Feminino").map((row) => row.total_year));
    document.getElementById("metric-share-label").textContent = "Participação feminina";
    setMetric(
      "metric-share",
      totalCases ? formatPercent((female / totalCases) * 100) : "-",
      "metric-share-note",
      `${formatInteger(female)} mulheres · ${formatInteger(totalCases - female)} homens`
    );
  } else {
    document.getElementById("metric-share-label").textContent = `Peso do sexo ${selectedSex.toLowerCase()}`;
    setMetric(
      "metric-share",
      scopeTotal ? formatPercent((totalCases / scopeTotal) * 100) : "-",
      "metric-share-note",
      `de ${formatInteger(scopeTotal)} casos nos estados selecionados`
    );
  }

  setMetric(
    "metric-state",
    dominant && dominant.total > 0 ? formatStateLabel(dominant.state) : "-",
    "metric-state-note",
    dominant && totalCases ? `${formatPercent((dominant.total / totalCases) * 100)} dos casos do recorte` : "Sem registros"
  );
}

function setMetric(valueId, value, noteId, note) {
  document.getElementById(valueId).textContent = value;
  document.getElementById(noteId).textContent = note;
}

function renderTrendChart(rows) {
  const traces = [];
  const annotations = [];
  const sexes = activeSexes();
  const lastYear = years()[years().length - 1];

  sexes.forEach((sex) => {
    const y = seriesByYear(rows.filter((row) => row.sex_label === sex));
    const color = theme.sex[sex];
    traces.push({
      type: "scatter",
      mode: "lines+markers",
      name: sex,
      x: years(),
      y,
      line: { color, width: 2.5 },
      marker: { size: fs(7), color, line: { color: theme.panel, width: 1.5 } },
      fill: sexes.length === 1 ? "tozeroy" : "none",
      fillcolor: hexToRgba(color, 0.1),
      hovertemplate: `${sex}: <b>%{y:,.0f}</b><extra></extra>`,
    });
    annotations.push({
      x: lastYear,
      y: y[y.length - 1],
      xanchor: "left",
      xshift: 12,
      text: `<b>${sex}</b> ${formatInteger(y[y.length - 1])}`,
      showarrow: false,
      font: { color: theme.text, size: fs(12) },
    });
  });

  const total = seriesByYear(rows);
  const peakIndex = total.indexOf(Math.max(...total));
  document.getElementById("trend-note").textContent = total[peakIndex] > 0
    ? `Pico do recorte em ${years()[peakIndex]}, com ${formatInteger(total[peakIndex])} notificações no ano.`
    : "Sem notificações no recorte atual.";

  Plotly.react(
    document.getElementById("trend-chart"),
    traces,
    baseLayout({
      margin: { t: 16, r: fs(isNarrow() ? 92 : 120), b: 40, l: 52 },
      hovermode: "x unified",
      separators: ",.",
      xaxis: yearAxis({ range: [2006.5, 2025.5], dtick: isNarrow() ? 6 : 2, showspikes: true, spikemode: "across", spikecolor: theme.axis, spikethickness: 1, spikedash: "dot" }),
      yaxis: axis({ title: { text: "Notificações", font: { color: theme.muted, size: fs(12) } }, rangemode: "tozero", fixedrange: true }),
      annotations,
    }),
    CHART_CONFIG
  );
}

function renderShareChart(stateRows) {
  const female = seriesByYear(stateRows.filter((row) => row.sex_label === "Feminino"));
  const total = seriesByYear(stateRows);
  const share = female.map((value, index) => (total[index] > 0 ? (value / total[index]) * 100 : null));
  const overall = sum(total) ? (sum(female) / sum(total)) * 100 : 0;

  document.getElementById("share-note").textContent =
    `Nos estados selecionados, ${formatPercent(overall)} dos casos são de mulheres. A linha pontilhada marca a paridade (50%). Este gráfico ignora o filtro de sexo.`;

  Plotly.react(
    document.getElementById("share-chart"),
    [
      {
        type: "bar",
        x: years(),
        y: share,
        customdata: total,
        marker: { color: share.map((value) => (value !== null && value >= 50 ? theme.sex.Feminino : hexToRgba(theme.sex.Feminino, 0.45))) },
        hovertemplate: "%{x}<br>Mulheres: <b>%{y:.1f}%</b><br>Total do ano: %{customdata:,.0f}<extra></extra>",
      },
    ],
    baseLayout({
      margin: { t: 16, r: 16, b: 40, l: 44 },
      bargap: 0.25,
      barcornerradius: 4,
      separators: ",.",
      xaxis: yearAxis({ dtick: 3 }),
      yaxis: axis({ range: [0, 100], ticksuffix: "%", dtick: 25, fixedrange: true }),
      shapes: [
        {
          type: "line",
          xref: "paper",
          x0: 0,
          x1: 1,
          y0: 50,
          y1: 50,
          line: { color: theme.muted, width: 1, dash: "dot" },
        },
      ],
    }),
    CHART_CONFIG
  );
}

function renderHeatmap(rows) {
  const states = sortStatesByTotal(selectedStates);
  const grouped = new Map();

  rows.forEach((row) => {
    const key = `${row.state}::${row.year}`;
    grouped.set(key, (grouped.get(key) || 0) + row.total_year);
  });

  const absoluteZ = states.map((state) => years().map((year) => grouped.get(`${state}::${year}`) || 0));
  const relativeZ = absoluteZ.map((series) => {
    const maxValue = Math.max(...series, 0);
    return series.map((value) => (maxValue > 0 ? value / maxValue : 0));
  });
  const isRelative = heatmapMode === "relative";
  const z = isRelative ? relativeZ : absoluteZ;
  const zmax = isRelative ? 1 : Math.max(1, ...absoluteZ.flat());
  const text = absoluteZ.map((series) => series.map((value) => (value > 0 ? formatInteger(value) : "")));
  // Texto claro sobre células escuras, escuro sobre células claras.
  const dark = document.documentElement.dataset.theme === "dark";
  const scale = theme.heat.map((color, index) => [index / (theme.heat.length - 1), color]);

  document.getElementById("heatmap-note").textContent = isRelative
    ? "Cada linha é escalada pelo pico do próprio estado (x / máx). Assim a variação de estados pequenos fica visível. Os números nas células são casos absolutos."
    : "Escala única para todos os estados. Mostra o peso real de cada um, mas São Paulo domina a escala.";

  const textColors = z.map((series) =>
    series.map((value) => {
      const strong = value / zmax > 0.55;
      return dark ? (strong ? "#0b2523" : "#e6f1f0") : strong ? "#ffffff" : "#16313a";
    })
  );

  const chartNode = document.getElementById("heatmap-chart");
  const traces = [
    {
      type: "heatmap",
      x: years(),
      y: states.map(formatStateLabel),
      z,
      zmin: 0,
      zmax,
      xgap: 3,
      ygap: 3,
      customdata: absoluteZ,
      colorscale: scale,
      showscale: chartNode.clientWidth > 560,
      colorbar: {
        thickness: 10,
        outlinewidth: 0,
        len: 0.9,
        tickfont: { color: theme.muted, size: fs(11) },
        tickformat: isRelative ? ".0%" : ",.0f",
      },
      hovertemplate: isRelative
        ? "<b>%{y}</b> · %{x}<br>Casos: %{customdata:,.0f}<br>%{z:.0%} do pico do estado<extra></extra>"
        : "<b>%{y}</b> · %{x}<br>Casos: %{customdata:,.0f}<extra></extra>",
    },
  ];

  const annotations = [];
  states.forEach((state, rowIndex) => {
    years().forEach((year, colIndex) => {
      if (!text[rowIndex][colIndex]) {
        return;
      }
      annotations.push({
        x: year,
        y: formatStateLabel(state),
        text: text[rowIndex][colIndex],
        showarrow: false,
        font: { size: fs(11), color: textColors[rowIndex][colIndex] },
      });
    });
  });

  const heatHeight = Math.max(220, states.length * fs(54) + fs(70));
  chartNode.style.minHeight = `${heatHeight}px`;

  Plotly.react(
    chartNode,
    traces,
    baseLayout({
      margin: { t: 10, r: 10, b: 36, l: 110 },
      separators: ",.",
      height: heatHeight,
      xaxis: axis({ showgrid: false, dtick: chartNode.clientWidth > 760 ? 1 : 6, tick0: 2007, tickangle: 0, fixedrange: true, ticks: "", tickfont: { color: theme.muted, size: fs(11) } }),
      yaxis: axis({ showgrid: false, autorange: "reversed", fixedrange: true, ticks: "", tickfont: { color: theme.text, size: fs(13) } }),
      annotations: chartNode.clientWidth > 760 ? annotations : [],
    }),
    CHART_CONFIG
  );
}

function isNarrow() {
  return window.innerWidth <= 720;
}

function multiplesColumns() {
  const width = document.getElementById("multiples-chart").clientWidth || window.innerWidth;
  return Math.max(1, Math.min(5, Math.floor(width / fs(250))));
}

function renderMultiples(rows) {
  const states = sortStatesByTotal(selectedStates);
  const columns = Math.min(multiplesColumns(), states.length);
  const rowCount = Math.ceil(states.length / columns);
  const gapX = columns > 1 ? 0.05 : 0;
  const gapY = rowCount > 1 ? 0.12 / rowCount + 0.06 : 0;
  const cellWidth = (1 - gapX * (columns - 1)) / columns;
  const cellHeight = (1 - gapY * (rowCount - 1)) / rowCount;
  const sexes = activeSexes();

  const traces = [];
  const layout = baseLayout({
    showlegend: sexes.length > 1,
    legend: { orientation: "h", x: 1, xanchor: "right", y: 0.99, yanchor: "top", yref: "container", traceorder: "normal", font: { color: theme.muted, size: fs(12) } },
    margin: { t: 44, r: 12, b: 30, l: 40 },
    hovermode: "x unified",
    separators: ",.",
    height: rowCount * fs(210) + fs(40),
    annotations: [],
  });

  states.forEach((state, index) => {
    const col = index % columns;
    const row = Math.floor(index / columns);
    const suffix = index === 0 ? "" : String(index + 1);
    const x0 = col * (cellWidth + gapX);
    const yTop = 1 - row * (cellHeight + gapY);
    const stateRows = rows.filter((item) => item.state === state);
    const stateTotal = sum(stateRows.map((item) => item.total_year));

    sexes.forEach((sex) => {
      traces.push({
        type: "scatter",
        mode: "lines",
        name: sex,
        x: years(),
        y: seriesByYear(stateRows.filter((item) => item.sex_label === sex)),
        xaxis: `x${suffix}`,
        yaxis: `y${suffix}`,
        line: { color: theme.sex[sex], width: 2 },
        showlegend: index === 0 && sexes.length > 1,
        hovertemplate: `${sex}: <b>%{y:,.0f}</b><extra></extra>`,
      });
    });

    layout[`xaxis${suffix}`] = yearAxis({
      domain: [x0, x0 + cellWidth],
      anchor: `y${suffix}`,
      dtick: 9,
      tick0: years()[0],
      showspikes: true,
      spikemode: "across",
      spikecolor: theme.axis,
      spikethickness: 1,
      spikedash: "dot",
    });
    layout[`yaxis${suffix}`] = axis({
      domain: [yTop - cellHeight, yTop],
      anchor: `x${suffix}`,
      rangemode: "tozero",
      nticks: 4,
      fixedrange: true,
    });
    layout.annotations.push({
      xref: "paper",
      yref: "paper",
      x: x0,
      y: yTop,
      xanchor: "left",
      yanchor: "bottom",
      yshift: 8,
      text: `<b>${formatStateLabel(state)}</b>  <span style="color:${theme.muted}">${formatInteger(stateTotal)} casos</span>`,
      showarrow: false,
      font: { family: FONT_BODY, size: fs(13), color: theme.text },
    });
  });

  const chartNode = document.getElementById("multiples-chart");
  chartNode.style.minHeight = `${layout.height}px`;
  Plotly.react(chartNode, traces, layout, CHART_CONFIG);
}

function renderStatesChart(stateRows) {
  const sexes = activeSexes();
  const scoped = stateRows.filter((row) => sexes.includes(row.sex_label));
  const ranked = totalsByState(scoped);
  const scopeTotal = sum(ranked.map((item) => item.total));
  const labels = ranked.map((item) => formatStateLabel(item.state));

  document.getElementById("states-note").textContent = selectedSex === "Todos"
    ? "Barras empilhadas por sexo. O rótulo mostra o total e a participação do estado no recorte."
    : `Somente ${selectedSex.toLowerCase()}. O rótulo mostra o total e a participação do estado no recorte.`;

  const traces = sexes.map((sex) => {
    const values = ranked.map((item) =>
      sum(scoped.filter((row) => row.state === item.state && row.sex_label === sex).map((row) => row.total_year))
    );
    return {
      type: "bar",
      orientation: "h",
      name: sex,
      y: labels,
      x: values,
      customdata: ranked.map((item, index) => (item.total ? (values[index] / item.total) * 100 : 0)),
      marker: { color: theme.sex[sex], line: { color: theme.panel, width: 2 } },
      hovertemplate: `<b>%{y}</b><br>${sex}: %{x:,.0f} (%{customdata:.1f}% do estado)<extra></extra>`,
    };
  });

  const maxTotal = Math.max(1, ...ranked.map((item) => item.total));
  const annotations = ranked.map((item, index) => ({
    x: item.total,
    y: labels[index],
    xanchor: "left",
    xshift: 8,
    text: `<b>${formatInteger(item.total)}</b>  <span style="color:${theme.muted}">${scopeTotal ? formatPercent((item.total / scopeTotal) * 100) : "0%"}</span>`,
    showarrow: false,
    font: { color: theme.text, size: fs(12) },
  }));

  Plotly.react(
    document.getElementById("states-chart"),
    traces,
    baseLayout({
      barmode: "stack",
      bargap: 0.38,
      barcornerradius: 4,
      separators: ",.",
      showlegend: sexes.length > 1,
      legend: { orientation: "h", x: 0, y: 1.08, traceorder: "normal", font: { color: theme.muted, size: fs(12) } },
      margin: { t: 30, r: 24, b: 40, l: 120 },
      xaxis: axis({ range: [0, maxTotal * (isNarrow() ? 1.6 : 1.28)], fixedrange: true, title: { text: "Notificações", font: { color: theme.muted, size: fs(12) } } }),
      yaxis: axis({ autorange: "reversed", showgrid: false, fixedrange: true, ticks: "", tickfont: { color: theme.text, size: fs(13) } }),
      annotations,
    }),
    CHART_CONFIG
  );
}

function renderToxicChart(rows) {
  const sexes = activeSexes();
  const grouped = {};

  rows.forEach((row) => {
    if (!grouped[row.toxic_group]) {
      grouped[row.toxic_group] = { Masculino: 0, Feminino: 0, total: 0 };
    }
    grouped[row.toxic_group][row.sex_label] += row.count;
    grouped[row.toxic_group].total += row.count;
  });

  const ranked = Object.entries(grouped)
    .map(([toxicGroup, values]) => ({ toxicGroup, ...values }))
    .filter((item) => item.total > 0)
    .sort((left, right) => right.total - left.total);

  // Grupos além do top N são agregados em "Demais grupos" para manter o gráfico legível.
  const head = ranked.slice(0, TOXIC_TOP_N);
  const tail = ranked.slice(TOXIC_TOP_N);
  if (tail.length) {
    head.push({
      toxicGroup: `Demais grupos (${tail.length})`,
      Masculino: sum(tail.map((item) => item.Masculino)),
      Feminino: sum(tail.map((item) => item.Feminino)),
      total: sum(tail.map((item) => item.total)),
    });
  }

  const sexTotals = Object.fromEntries(SEXES.map((sex) => [sex, sum(ranked.map((item) => item[sex]))]));
  const isShare = toxicMode === "share";
  const labels = head.map((item) => formatToxicGroupLabel(item.toxicGroup));

  document.getElementById("toxic-note").textContent = isShare
    ? "Percentual dentro de cada sexo. Compara o perfil de agentes entre mulheres e homens."
    : `Os ${TOXIC_TOP_N} grupos mais frequentes no recorte; os demais aparecem agregados.`;

  const traces = sexes.map((sex) => {
    const values = head.map((item) =>
      isShare ? (sexTotals[sex] ? (item[sex] / sexTotals[sex]) * 100 : 0) : item[sex]
    );
    return {
      type: "bar",
      orientation: "h",
      name: sex,
      y: labels,
      x: values,
      text: values.map((value) => (isShare ? `${formatDecimal(value)}%` : formatInteger(value))),
      textposition: "outside",
      cliponaxis: false,
      textfont: { color: theme.muted, size: fs(11) },
      marker: { color: theme.sex[sex] },
      hovertemplate: isShare
        ? `<b>%{y}</b><br>${sex}: %{x:.1f}% dos casos do sexo<extra></extra>`
        : `<b>%{y}</b><br>${sex}: %{x:,.0f}<extra></extra>`,
    };
  });

  const maxValue = Math.max(1, ...traces.flatMap((trace) => trace.x));

  Plotly.react(
    document.getElementById("toxic-chart"),
    traces,
    baseLayout({
      barmode: "group",
      bargap: 0.3,
      bargroupgap: 0.08,
      barcornerradius: 3,
      separators: ",.",
      showlegend: sexes.length > 1,
      legend: { orientation: "h", x: 0, y: 1.08, traceorder: "normal", font: { color: theme.muted, size: fs(12) } },
      margin: { t: 30, r: 24, b: 40, l: 170 },
      xaxis: axis({
        range: [0, maxValue * 1.18],
        fixedrange: true,
        ticksuffix: isShare ? "%" : "",
        title: { text: isShare ? "% dos casos do sexo" : "Notificações", font: { color: theme.muted, size: fs(12) } },
      }),
      yaxis: axis({ autorange: "reversed", showgrid: false, fixedrange: true, ticks: "", tickfont: { color: theme.text, size: fs(12) } }),
    }),
    CHART_CONFIG
  );
}

function renderStateTable(stateRows) {
  const head = document.getElementById("state-summary-head");
  const body = document.getElementById("state-summary-body");
  const note = document.getElementById("table-note");
  const sexes = activeSexes();

  const rows = sortStatesByTotal(selectedStates).map((state) => {
    const scoped = stateRows.filter((row) => row.state === state);
    const female = sum(scoped.filter((row) => row.sex_label === "Feminino").map((row) => row.total_year));
    const male = sum(scoped.filter((row) => row.sex_label === "Masculino").map((row) => row.total_year));
    const value = sexes.length === 2 ? female + male : selectedSex === "Feminino" ? female : male;
    return { state, female, male, total: female + male, value };
  });
  const scopeValue = sum(rows.map((row) => row.value));

  head.innerHTML = "";
  body.innerHTML = "";

  if (selectedSex === "Todos") {
    note.textContent = "Os dois sexos e o total acumulado nos estados selecionados.";
    head.innerHTML = `
      <th>Estado</th>
      <th>Feminino</th>
      <th>Masculino</th>
      <th>Total</th>
      <th>F / M</th>
      <th>Participação</th>
    `;
  } else {
    note.textContent = `Somente o sexo ${selectedSex.toLowerCase()}, com a participação de cada estado no recorte.`;
    head.innerHTML = `
      <th>Estado</th>
      <th>${selectedSex}</th>
      <th>Participação</th>
    `;
  }

  rows.forEach((row) => {
    const share = scopeValue ? (row.value / scopeValue) * 100 : 0;
    const shareCell = `
      <div class="share-cell">
        <span>${formatPercent(share)}</span>
        <div class="share-bar" aria-hidden="true"><span style="width:${share.toFixed(1)}%"></span></div>
      </div>`;
    const tr = document.createElement("tr");

    if (selectedSex === "Todos") {
      const femaleShare = row.total ? (row.female / row.total) * 100 : 0;
      tr.innerHTML = `
        <td>${formatStateLabel(row.state)}</td>
        <td>${formatInteger(row.female)}</td>
        <td>${formatInteger(row.male)}</td>
        <td><strong>${formatInteger(row.total)}</strong></td>
        <td>
          <div class="share-cell" title="${formatPercent(femaleShare)} feminino">
            <span>${formatPercent(femaleShare)}</span>
            <div class="split-bar" aria-hidden="true">
              <span style="width:${femaleShare.toFixed(1)}%; background:${theme.sex.Feminino}"></span>
              <span style="width:${(100 - femaleShare).toFixed(1)}%; background:${theme.sex.Masculino}"></span>
            </div>
          </div>
        </td>
        <td>${shareCell}</td>
      `;
    } else {
      tr.innerHTML = `
        <td>${formatStateLabel(row.state)}</td>
        <td><strong>${formatInteger(row.value)}</strong></td>
        <td>${shareCell}</td>
      `;
    }
    body.appendChild(tr);
  });
}

function renderInsights(rows, stateRows, tidyRows) {
  const list = document.getElementById("insight-list");
  list.innerHTML = "";

  buildDynamicInsights(rows, stateRows, tidyRows).forEach((insight) => {
    const item = document.createElement("li");
    item.innerHTML = insight;
    list.appendChild(item);
  });
}

function buildDynamicInsights(rows, stateRows, tidyRows) {
  const totalCases = sum(rows.map((row) => row.total_year));
  if (!totalCases) {
    return ["Não há registros para o recorte atual."];
  }

  const topState = totalsByState(rows)[0];
  const series = seriesByYear(rows);
  const peakIndex = series.indexOf(Math.max(...series));
  const groupedToxic = Object.entries(groupBy(tidyRows, "toxic_group"))
    .map(([toxicGroup, toxicRows]) => ({ toxicGroup, total: sum(toxicRows.map((row) => row.count)) }))
    .sort((left, right) => right.total - left.total);
  const toxicTotal = sum(groupedToxic.map((item) => item.total));
  const topToxic = groupedToxic[0];

  // Comparação entre a primeira e a segunda metade da série.
  const half = Math.floor(series.length / 2);
  const firstHalf = sum(series.slice(0, half));
  const secondHalf = sum(series.slice(series.length - half));

  const insights = [
    `<strong>${formatStateLabel(topState.state)}</strong> responde por ${formatPercent((topState.total / totalCases) * 100)} do recorte, com ${formatInteger(topState.total)} notificações.`,
    `O pico anual ocorre em <strong>${years()[peakIndex]}</strong>, com ${formatInteger(series[peakIndex])} notificações.`,
  ];

  if (firstHalf > 0) {
    insights.push(
      `Os últimos ${half} anos somam <strong>${formatDecimal(secondHalf / firstHalf)}×</strong> o volume dos primeiros ${half} anos da série.`
    );
  }

  if (topToxic && toxicTotal) {
    insights.push(
      `<strong>${formatToxicGroupLabel(topToxic.toxicGroup)}</strong> é o grupo tóxico mais frequente, com ${formatPercent((topToxic.total / toxicTotal) * 100)} dos agentes registrados.`
    );
  }

  if (selectedSex === "Todos") {
    const femaleTotal = sum(rows.filter((row) => row.sex_label === "Feminino").map((row) => row.total_year));
    insights.push(
      `Mulheres representam <strong>${formatPercent((femaleTotal / totalCases) * 100)}</strong> do recorte, frente a ${formatInteger(totalCases - femaleTotal)} casos masculinos.`
    );
  } else {
    const scopeTotal = sum(stateRows.map((row) => row.total_year));
    insights.push(
      `O sexo ${selectedSex.toLowerCase()} responde por <strong>${formatPercent((totalCases / scopeTotal) * 100)}</strong> dos casos nos estados selecionados.`
    );
  }

  return insights;
}

/* ---------- Background ---------- */

// Campo de pontos que ondula lentamente e reage ao cursor, com duas linhas de série
// ao fundo. Fica atrás do conteúdo, pausa com a aba oculta e respeita reduced-motion.
function initBackground() {
  const canvas = document.getElementById("bg-canvas");
  const glow = document.getElementById("bg-glow");
  const ctx = canvas.getContext("2d");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const pointer = { x: -9999, y: -9999, tx: -9999, ty: -9999, strength: 0, target: 0 };
  let width = 0;
  let height = 0;
  let spacing = 34;
  let frame = null;

  const resize = () => {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    spacing = width < 720 ? 30 : width > 2200 ? 40 : 34;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    if (reduceMotion) {
      draw(0);
    }
  };

  const draw = (time) => {
    const rgb = theme.dot || "19, 144, 130";
    const dark = document.documentElement.dataset.theme === "dark";
    const baseAlpha = dark ? 0.1 : 0.12;
    const radius = Math.max(180, Math.min(width, height) * 0.28);

    pointer.x += (pointer.tx - pointer.x) * 0.12;
    pointer.y += (pointer.ty - pointer.y) * 0.12;
    pointer.strength += (pointer.target - pointer.strength) * 0.06;

    ctx.clearRect(0, 0, width, height);

    const t = time * 0.00035;
    for (let y = spacing / 2; y < height; y += spacing) {
      for (let x = spacing / 2; x < width; x += spacing) {
        const wave = Math.sin(x * 0.0042 + t) + Math.cos(y * 0.0051 - t * 0.8) + Math.sin((x + y) * 0.0021 + t * 0.6);
        let alpha = baseAlpha * (0.45 + 0.55 * ((wave + 3) / 6));
        let size = 1.1;
        let px = x;
        let py = y;

        const dx = x - pointer.x;
        const dy = y - pointer.y;
        const distance = Math.hypot(dx, dy);
        if (distance < radius && pointer.strength > 0.01) {
          const k = (1 - distance / radius) ** 2 * pointer.strength;
          px += (dx / (distance || 1)) * k * 10;
          py += (dy / (distance || 1)) * k * 10;
          alpha += k * (dark ? 0.45 : 0.5);
          size += k * 1.6;
        }

        ctx.fillStyle = `rgba(${rgb}, ${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(px, py, size, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Duas linhas suaves, lembrando séries temporais, que se curvam perto do cursor.
    [0.32, 0.74].forEach((level, index) => {
      ctx.beginPath();
      for (let x = -20; x <= width + 20; x += 16) {
        const base = height * level
          + Math.sin(x * 0.0032 + t * (index ? 1.3 : 1)) * 38
          + Math.sin(x * 0.0011 - t * 0.7 + index) * 54;
        const dx = x - pointer.x;
        const pull = Math.exp(-(dx * dx) / (2 * 160 * 160)) * pointer.strength;
        const y = base + (pointer.y - base) * pull * 0.18;
        if (x === -20) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.strokeStyle = `rgba(${rgb}, ${dark ? 0.1 : 0.09})`;
      ctx.lineWidth = 1.4;
      ctx.stroke();
    });
  };

  const loop = (time) => {
    draw(time);
    frame = requestAnimationFrame(loop);
  };

  const moveTo = (x, y) => {
    pointer.tx = x;
    pointer.ty = y;
    if (pointer.x < -1000) {
      pointer.x = x;
      pointer.y = y;
    }
    pointer.target = 1;
    glow.style.transform = `translate3d(${x}px, ${y}px, 0)`;
    glow.classList.add("is-visible");
  };

  window.addEventListener("pointermove", (event) => moveTo(event.clientX, event.clientY), { passive: true });
  window.addEventListener("pointerdown", (event) => moveTo(event.clientX, event.clientY), { passive: true });
  document.addEventListener("pointerleave", () => {
    pointer.target = 0;
    glow.classList.remove("is-visible");
  });
  window.addEventListener("blur", () => {
    pointer.target = 0;
    glow.classList.remove("is-visible");
  });
  window.addEventListener("resize", resize);
  document.addEventListener("visibilitychange", () => {
    if (reduceMotion) {
      return;
    }
    if (document.hidden) {
      cancelAnimationFrame(frame);
      frame = null;
    } else if (!frame) {
      frame = requestAnimationFrame(loop);
    }
  });

  resize();
  if (!reduceMotion) {
    frame = requestAnimationFrame(loop);
  }
}

/* ---------- Utils ---------- */

function aggregateByYear(rows) {
  const totals = new Map();
  rows.forEach((row) => {
    totals.set(row.year, (totals.get(row.year) || 0) + row.total_year);
  });
  return totals;
}

function groupBy(rows, key) {
  return rows.reduce((accumulator, row) => {
    const value = row[key];
    if (!accumulator[value]) {
      accumulator[value] = [];
    }
    accumulator[value].push(row);
    return accumulator;
  }, {});
}

function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}

function formatInteger(value) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function formatDecimal(value) {
  return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value);
}

function formatPercent(value) {
  return `${formatDecimal(value)}%`;
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function formatStateLabel(value) {
  return STATE_LABELS[value] || value;
}

function formatStateList(values) {
  return values.map((value) => formatStateLabel(value));
}

function formatToxicGroupLabel(value) {
  return TOXIC_GROUP_LABELS[value] || value;
}
