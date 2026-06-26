const SEX_PALETTE = {
  Masculino: "#5B7FA3",
  Feminino: "#C06A6A",
};

const STATE_COLORS = {
  "Sao Paulo": "#5C7FA3",
  "Santa Catarina": "#7BA6C8",
  "Distrito Federal": "#88A86A",
  Paraiba: "#C08F63",
  Acre: "#B8778D",
};

const STATE_LABELS = {
  "Sao Paulo": "São Paulo",
  Paraiba: "Paraíba",
};

const TOXIC_GROUP_LABELS = {
  "Cosmético_higiene pessoal": "Cosmético e higiene pessoal",
};

const CHART_CONFIG = {
  displayModeBar: false,
  responsive: true,
};

const PLOT_LAYOUT_BASE = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  margin: { t: 30, r: 20, b: 50, l: 55 },
  font: {
    family: '"Source Sans 3", "Trebuchet MS", sans-serif',
    color: "#16313A",
  },
};

let dashboardData = null;
let selectedSex = "Todos";
let selectedStates = [];

document.addEventListener("DOMContentLoaded", async () => {
  try {
    dashboardData = await fetchDashboardData();
    selectedStates = [...dashboardData.metadata.states];

    hydrateMetadata();
    buildSexFilter();
    buildStateFilter();
    bindToolbarActions();
    renderDashboard();
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

function hydrateMetadata() {
  const { start_year: startYear, end_year: endYear, generated_at_utc: generatedAt } = dashboardData.metadata;
  document.getElementById("meta-period").textContent = `Período ${startYear} - ${endYear}`;
  document.getElementById("meta-generated").textContent = `Atualizado em ${formatDateTime(generatedAt)}`;
}

function buildSexFilter() {
  const container = document.getElementById("sex-filter");
  const options = ["Todos", "Masculino", "Feminino"];

  container.innerHTML = "";
  options.forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `segmented-button${option === selectedSex ? " is-active" : ""}`;
    button.textContent = option;
    button.setAttribute("aria-pressed", String(option === selectedSex));
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
  const states = dashboardData.metadata.states;

  container.innerHTML = "";

  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.className = `chip${selectedStates.length === states.length ? " is-active" : ""}`;
  allButton.textContent = "Todos";
  allButton.setAttribute("aria-pressed", String(selectedStates.length === states.length));
  allButton.title = "Selecionar todos os estados";
  allButton.addEventListener("click", () => {
    selectedStates = [...states];
    buildStateFilter();
    renderDashboard();
  });
  container.appendChild(allButton);

  states.forEach((state) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `chip${selectedStates.includes(state) ? " is-active" : ""}`;
    button.textContent = formatStateLabel(state);
    button.setAttribute("aria-pressed", String(selectedStates.includes(state)));
    button.title = "Clique para incluir ou remover este estado do recorte";
    button.addEventListener("click", () => toggleStateSelection(state));
    container.appendChild(button);
  });
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

function toggleStateSelection(state) {
  if (selectedStates.includes(state)) {
    selectedStates = selectedStates.filter((item) => item !== state);
  } else {
    selectedStates = [...selectedStates, state];
  }

  if (!selectedStates.length) {
    selectedStates = [...dashboardData.metadata.states];
  }

  buildStateFilter();
  renderDashboard();
}

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

function renderDashboard() {
  const filteredYearTotals = getFilteredYearTotals();
  const stateScopedYearTotals = getStateScopedYearTotals();
  const filteredTidyCounts = getFilteredTidyCounts();

  renderFilterSummary(filteredYearTotals);
  renderMetrics(filteredYearTotals);
  renderTrendChart(filteredYearTotals);
  renderHeatmap(filteredYearTotals);
  renderPieCharts(stateScopedYearTotals);
  renderToxicChart(filteredTidyCounts);
  renderDetailChart(filteredYearTotals);
  renderStateTable(filteredYearTotals);
  renderInsights(filteredYearTotals, filteredTidyCounts);
}

function renderFilterSummary(rows) {
  const titleNode = document.getElementById("filter-summary-title");
  const textNode = document.getElementById("filter-summary-text");
  const totalStates = dashboardData.metadata.states.length;
  const selectedStateLabels = formatStateList(selectedStates);
  const stateLabel =
    selectedStates.length === totalStates
      ? "Todos os estados"
      : `${selectedStates.length} estado(s): ${selectedStateLabels.join(", ")}`;
  const sexLabel = selectedSex === "Todos" ? "todos os sexos" : selectedSex.toLowerCase();
  const totalCases = sum(rows.map((row) => row.total_year));

  titleNode.textContent = `${stateLabel} | ${sexLabel}`;
  textNode.textContent = `${formatInteger(totalCases)} casos no recorte atual, com visualizações sincronizadas para tendência, heatmap, tabela e insights.`;
}

function renderMetrics(rows) {
  const totalCases = sum(rows.map((row) => row.total_year));
  const latestYear = Math.max(...dashboardData.metadata.years);
  const latestYearTotal = sum(rows.filter((row) => row.year === latestYear).map((row) => row.total_year));
  const groupedByState = groupBy(rows, "state");
  const dominantEntry = Object.entries(groupedByState)
    .map(([state, stateRows]) => ({
      state,
      total: sum(stateRows.map((row) => row.total_year)),
    }))
    .sort((left, right) => right.total - left.total)[0];
  const yearsWithCases = new Set(rows.filter((row) => row.total_year > 0).map((row) => row.year)).size;

  setMetric(
    "metric-total",
    formatInteger(totalCases),
    "metric-total-note",
    `${selectedStates.length} estado(s) no recorte`
  );
  setMetric("metric-latest", String(latestYear), "metric-latest-note", `${formatInteger(latestYearTotal)} casos`);
  setMetric(
    "metric-state",
    dominantEntry ? formatStateLabel(dominantEntry.state) : "-",
    "metric-state-note",
    dominantEntry ? `${formatInteger(dominantEntry.total)} casos acumulados` : "Sem registros"
  );
  setMetric(
    "metric-active-years",
    String(yearsWithCases),
    "metric-active-years-note",
    selectedSex === "Todos" ? "anos com pelo menos uma notificação" : `anos com ${selectedSex.toLowerCase()}`
  );
}

function setMetric(valueId, value, noteId, note) {
  document.getElementById(valueId).textContent = value;
  document.getElementById(noteId).textContent = note;
}

function renderTrendChart(rows) {
  const chartNode = document.getElementById("trend-chart");
  const traces = [];

  if (selectedSex === "Todos") {
    ["Masculino", "Feminino"].forEach((sex) => {
      const sexRows = rows.filter((row) => row.sex_label === sex);
      const yearly = aggregateByYear(sexRows);
      traces.push({
        type: "scatter",
        mode: "lines+markers",
        name: sex,
        x: dashboardData.metadata.years,
        y: dashboardData.metadata.years.map((year) => yearly.get(year) || 0),
        line: { color: SEX_PALETTE[sex], width: 3 },
        marker: { size: 8 },
      });
    });
  } else {
    const yearly = aggregateByYear(rows);
    traces.push({
      type: "scatter",
      mode: "lines+markers",
      name: selectedSex,
      x: dashboardData.metadata.years,
      y: dashboardData.metadata.years.map((year) => yearly.get(year) || 0),
      line: { color: SEX_PALETTE[selectedSex], width: 3.4 },
      marker: { size: 8 },
    });
  }

  Plotly.react(
    chartNode,
    traces,
    {
      ...PLOT_LAYOUT_BASE,
      xaxis: { title: "Ano", tickmode: "linear" },
      yaxis: { title: "Notificações" },
      legend: { orientation: "h", y: 1.14 },
    },
    CHART_CONFIG
  );
}

function renderHeatmap(rows) {
  const years = dashboardData.metadata.years;
  const states = [...selectedStates];
  const grouped = new Map();

  rows.forEach((row) => {
    const key = `${row.state}::${row.year}`;
    grouped.set(key, (grouped.get(key) || 0) + row.total_year);
  });

  const absoluteZ = states.map((state) =>
    years.map((year) => grouped.get(`${state}::${year}`) || 0)
  );
  const z = absoluteZ.map((stateSeries) => {
    const maxValue = Math.max(...stateSeries, 0);
    return stateSeries.map((value) => (maxValue > 0 ? value / maxValue : 0));
  });

  Plotly.react(
    document.getElementById("heatmap-chart"),
    [
      {
        type: "heatmap",
        x: years,
        y: states,
        z,
        zmin: 0,
        zmax: 1,
        customdata: absoluteZ,
        colorscale: [
          [0.0, "#FFF9E8"],
          [0.2, "#FEE7A8"],
          [0.45, "#FDB366"],
          [0.7, "#F46D43"],
          [0.88, "#D73027"],
          [1.0, "#A50026"],
        ],
        colorbar: {
          title: "x / max(x)",
        },
        hovertemplate:
          "Estado: %{y}<br>Ano: %{x}<br>Casos: %{customdata:,.0f}<br>Índice relativo: %{z:.2f}<extra></extra>",
      },
    ],
    {
      ...PLOT_LAYOUT_BASE,
      margin: { t: 30, r: 18, b: 50, l: 90 },
      xaxis: { title: "Ano", tickmode: "linear" },
      yaxis: { title: "Estado", automargin: true },
    },
    CHART_CONFIG
  );
}

function renderPieCharts(rows) {
  const pieNote = document.getElementById("pie-note");

  if (selectedSex === "Todos") {
    pieNote.textContent = "Os três gráficos comparam total, feminino e masculino dentro dos estados selecionados.";
    renderPieChart("pie-total-chart", rows, "Total por estado", null);
    renderPieChart("pie-feminino-chart", rows, "Feminino por estado", "Feminino");
    renderPieChart("pie-masculino-chart", rows, "Masculino por estado", "Masculino");
    return;
  }

  const comparatorSex = selectedSex === "Feminino" ? "Masculino" : "Feminino";
  pieNote.textContent = `O primeiro gráfico segue o filtro ativo; os outros dois mantêm contexto comparativo nos mesmos estados.`;
  renderPieChart("pie-total-chart", rows, `Recorte atual (${selectedSex})`, selectedSex);
  renderPieChart("pie-feminino-chart", rows, "Total por estado", null);
  renderPieChart("pie-masculino-chart", rows, `${comparatorSex} por estado`, comparatorSex);
}

function renderPieChart(elementId, rows, title, sexFilter) {
  const baseRows = sexFilter ? rows.filter((row) => row.sex_label === sexFilter) : rows;
  const grouped = Object.entries(groupBy(baseRows, "state"))
    .map(([state, stateRows]) => ({
      state,
      total: sum(stateRows.map((row) => row.total_year)),
    }))
    .sort((left, right) => right.total - left.total);

  Plotly.react(
    document.getElementById(elementId),
    [
      {
        type: "pie",
        labels: grouped.map((item) => item.state),
        values: grouped.map((item) => item.total),
        sort: false,
        marker: {
          colors: grouped.map((item) => STATE_COLORS[item.state] || "#86A7B5"),
          line: { color: "#FFFFFF", width: 1.5 },
        },
        textinfo: "label+percent",
        hovertemplate: "%{label}<br>Casos: %{value:,.0f}<br>Participacao: %{percent}<extra></extra>",
      },
    ],
    {
      ...PLOT_LAYOUT_BASE,
      title: { text: title, x: 0.02, xanchor: "left", font: { family: '"Sora", "Trebuchet MS", sans-serif', size: 18 } },
      margin: { t: 54, r: 10, b: 10, l: 10 },
      showlegend: false,
    },
    CHART_CONFIG
  );
}

function renderToxicChart(rows) {
  const grouped = {};

  rows.forEach((row) => {
    const toxicGroup = row.toxic_group;
    if (!grouped[toxicGroup]) {
      grouped[toxicGroup] = { Masculino: 0, Feminino: 0, total: 0 };
    }
    grouped[toxicGroup][row.sex_label] += row.count;
    grouped[toxicGroup].total += row.count;
  });

  const ranked = Object.entries(grouped)
    .map(([toxicGroup, values]) => ({ toxicGroup, ...values }))
    .sort((left, right) => right.total - left.total)
    .slice(0, 10)
    .reverse();

  let traces;
  if (selectedSex === "Todos") {
    traces = ["Masculino", "Feminino"].map((sex) => ({
      type: "bar",
      orientation: "h",
      name: sex,
      y: ranked.map((item) => formatToxicGroupLabel(item.toxicGroup)),
      x: ranked.map((item) => item[sex]),
      marker: { color: SEX_PALETTE[sex] },
    }));
  } else {
    traces = [
      {
        type: "bar",
        orientation: "h",
        name: selectedSex,
        y: ranked.map((item) => formatToxicGroupLabel(item.toxicGroup)),
        x: ranked.map((item) => item[selectedSex]),
        marker: { color: SEX_PALETTE[selectedSex] },
      },
    ];
  }

  Plotly.react(
    document.getElementById("toxic-chart"),
    traces,
    {
      ...PLOT_LAYOUT_BASE,
      margin: { t: 30, r: 20, b: 50, l: 180 },
      barmode: selectedSex === "Todos" ? "group" : "relative",
      xaxis: { title: "Notificações" },
      yaxis: { title: "" },
      legend: { orientation: "h", y: 1.12 },
    },
    CHART_CONFIG
  );
}

function renderDetailChart(rows) {
  const note = document.getElementById("detail-note");
  const groupedByState = Object.entries(groupBy(rows, "state"))
    .map(([state, stateRows]) => ({
      state,
      total: sum(stateRows.map((row) => row.total_year)),
    }))
    .sort((left, right) => right.total - left.total);
  const detailState = groupedByState[0]?.state || selectedStates[0] || null;
  const detailTotal = groupedByState[0]?.total || 0;
  const detailRows = detailState ? rows.filter((row) => row.state === detailState) : [];
  const sexes = selectedSex === "Todos" ? ["Masculino", "Feminino"] : [selectedSex];

  if (!detailState) {
    note.textContent = "Sem estado disponível para o recorte atual.";
  } else if (detailTotal > 0) {
    note.textContent = `Foco automático em ${formatStateLabel(detailState)}, com ${formatInteger(detailTotal)} casos acumulados no recorte atual.`;
  } else {
    note.textContent = `Foco automático em ${formatStateLabel(detailState)}. No recorte atual, os estados selecionados não registram notificações.`;
  }

  const traces = sexes.map((sex) => {
    const sexRows = detailRows.filter((row) => row.sex_label === sex);
    const yearly = aggregateByYear(sexRows);
    return {
      type: "scatter",
      mode: "lines+markers",
      name: sex,
      x: dashboardData.metadata.years,
      y: dashboardData.metadata.years.map((year) => yearly.get(year) || 0),
      line: { color: SEX_PALETTE[sex], width: 3 },
      marker: { size: 8 },
    };
  });

  Plotly.react(
    document.getElementById("detail-chart"),
    traces,
    {
      ...PLOT_LAYOUT_BASE,
      title: {
        text: detailState ? formatStateLabel(detailState) : "Estado",
        x: 0.02,
        xanchor: "left",
        font: { family: '"Sora", "Trebuchet MS", sans-serif', size: 18 },
      },
      xaxis: { title: "Ano", tickmode: "linear" },
      yaxis: { title: "Notificações" },
      legend: { orientation: "h", y: 1.14 },
    },
    CHART_CONFIG
  );
}

function renderStateTable(rows) {
  const groupedByState = groupBy(rows, "state");
  const head = document.getElementById("state-summary-head");
  const body = document.getElementById("state-summary-body");
  const note = document.getElementById("table-note");

  head.innerHTML = "";
  body.innerHTML = "";

  if (selectedSex === "Todos") {
    note.textContent = "Tabela consolidada com os dois sexos e total acumulado dentro do recorte de estados selecionado.";
    head.innerHTML = `
      <th>Estado</th>
      <th>Masculino</th>
      <th>Feminino</th>
      <th>Total</th>
    `;

    Object.entries(groupedByState)
      .map(([state, stateRows]) => {
        const male = sum(stateRows.filter((row) => row.sex_label === "Masculino").map((row) => row.total_year));
        const female = sum(stateRows.filter((row) => row.sex_label === "Feminino").map((row) => row.total_year));
        return {
          state,
          male,
          female,
          total: male + female,
        };
      })
      .sort((left, right) => right.total - left.total)
      .forEach((row) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${formatStateLabel(row.state)}</td>
          <td>${formatInteger(row.male)}</td>
          <td>${formatInteger(row.female)}</td>
          <td>${formatInteger(row.total)}</td>
        `;
        body.appendChild(tr);
      });
    return;
  }

  note.textContent = `Tabela focada apenas no recorte ${selectedSex.toLowerCase()}, com participação percentual por estado.`;
  head.innerHTML = `
    <th>Estado</th>
    <th>${selectedSex}</th>
    <th>% do recorte</th>
  `;

  const totalScope = sum(rows.map((row) => row.total_year));
  Object.entries(groupedByState)
    .map(([state, stateRows]) => {
      const total = sum(stateRows.map((row) => row.total_year));
      return {
        state,
        total,
        share: totalScope ? (total / totalScope) * 100 : 0,
      };
    })
    .sort((left, right) => right.total - left.total)
    .forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${formatStateLabel(row.state)}</td>
        <td>${formatInteger(row.total)}</td>
        <td>${row.share.toFixed(1)}%</td>
      `;
      body.appendChild(tr);
    });
}

function renderInsights(rows, tidyRows) {
  const list = document.getElementById("insight-list");
  const note = document.getElementById("insight-note");
  list.innerHTML = "";
  note.textContent = "Os destaques abaixo acompanham o recorte ativo de sexo e estados.";

  const insights = buildDynamicInsights(rows, tidyRows);

  insights.forEach((insight) => {
    const item = document.createElement("li");
    item.textContent = insight;
    list.appendChild(item);
  });
}

function buildDynamicInsights(rows, tidyRows) {
  if (!rows.length) {
    return ["Não há registros para o recorte atual."];
  }

  const totalCases = sum(rows.map((row) => row.total_year));
  const groupedByState = Object.entries(groupBy(rows, "state"))
    .map(([state, stateRows]) => ({
      state,
      total: sum(stateRows.map((row) => row.total_year)),
    }))
    .sort((left, right) => right.total - left.total);
  const groupedByYear = Object.entries(groupBy(rows, "year"))
    .map(([year, yearRows]) => ({
      year: Number(year),
      total: sum(yearRows.map((row) => row.total_year)),
    }))
    .sort((left, right) => right.total - left.total);
  const groupedToxic = Object.entries(groupBy(tidyRows, "toxic_group"))
    .map(([toxicGroup, toxicRows]) => ({
      toxicGroup,
      total: sum(toxicRows.map((row) => row.count)),
    }))
    .sort((left, right) => right.total - left.total);

  const topState = groupedByState[0];
  const peakYear = groupedByYear[0];
  const topToxic = groupedToxic[0];

  const insights = [
    `${formatInteger(totalCases)} casos compõem o recorte atual, distribuído por ${selectedStates.length} estado(s).`,
    `${formatStateLabel(topState.state)} lidera este recorte com ${formatInteger(topState.total)} notificações acumuladas.`,
    `O pico anual do recorte ocorre em ${peakYear.year}, com ${formatInteger(peakYear.total)} notificações.`,
  ];

  if (topToxic) {
    insights.push(`${formatToxicGroupLabel(topToxic.toxicGroup)} é o grupo tóxico mais frequente no recorte atual.`);
  }

  if (selectedSex === "Todos") {
    const maleTotal = sum(rows.filter((row) => row.sex_label === "Masculino").map((row) => row.total_year));
    const femaleTotal = sum(rows.filter((row) => row.sex_label === "Feminino").map((row) => row.total_year));
    const femaleShare = totalCases ? (femaleTotal / totalCases) * 100 : 0;
    insights.push(`Mulheres representam ${femaleShare.toFixed(1)}% do recorte, frente a ${formatInteger(maleTotal)} casos masculinos.`);
  }

  return insights;
}

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
  return new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
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
