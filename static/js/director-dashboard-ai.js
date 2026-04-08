(function () {
  const config = window.directorNeoDashboardConfig || {};
  const API_URL = config.apiUrl || "";

  const state = {
    payload: null,
    charts: {},
    loading: false,
  };

  const PRESETS = [
    { id: "today", name: "Bugun" },
    { id: "yesterday", name: "Kecha" },
    { id: "this_week", name: "Bu hafta" },
    { id: "this_month", name: "Bu oy" },
    { id: "last_month", name: "O'tgan oy" },
    { id: "this_quarter", name: "Bu chorak" },
    { id: "custom", name: "Maxsus" },
  ];

  const COLORS = {
    cyan: "#3ec8ff",
    blue: "#5d7dff",
    green: "#29d391",
    amber: "#ffb020",
    red: "#ff5d73",
    violet: "#8d6bff",
    muted: "rgba(146, 161, 187, 0.85)",
    grid: "rgba(255,255,255,0.05)",
    stroke: "rgba(255,255,255,0.08)",
  };

  const FILTER_KEYS = [
    "preset",
    "date_from",
    "date_to",
    "branch",
    "teacher",
    "group",
    "category",
  ];

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function toNumber(value) {
    if (value === null || value === undefined || value === "") return 0;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function formatNumber(value) {
    return new Intl.NumberFormat("uz-UZ").format(Math.round(toNumber(value)));
  }

  function formatMoney(value) {
    return `${formatNumber(value)} UZS`;
  }

  function formatCompactMoney(value) {
    const number = Math.abs(toNumber(value));
    const sign = toNumber(value) < 0 ? "-" : "";
    if (number >= 1e9) return `${sign}${(number / 1e9).toFixed(1)} mlrd UZS`;
    if (number >= 1e6) return `${sign}${(number / 1e6).toFixed(1)} mln UZS`;
    if (number >= 1e3) return `${sign}${Math.round(number / 1e3)} ming UZS`;
    return `${sign}${Math.round(number)} UZS`;
  }

  function formatPercent(value, digits = 1) {
    if (value === null || value === undefined || value === "") return "0%";
    const num = toNumber(value);
    return `${num.toFixed(digits).replace(/\.0$/, "")}%`;
  }

  function formatSignedPercent(value) {
    const num = toNumber(value);
    const prefix = num > 0 ? "+" : "";
    return `${prefix}${formatPercent(num)}`;
  }

  function formatDate(value) {
    if (!value) return "--";
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("uz-UZ", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(date);
  }

  function toneClass(value) {
    const text = String(value || "").toLowerCase();
    if (["critical", "danger", "close candidate", "stop"].includes(text)) return "bad";
    if (["high", "warning", "fix", "risky", "weak"].includes(text)) return "warn";
    if (["success", "grow", "strong", "stable", "good"].includes(text)) return "good";
    return "info";
  }

  function deltaClass(value) {
    const num = toNumber(value);
    if (num > 0) return "up";
    if (num < 0) return "down";
    return "";
  }

  function chartTooltip() {
    return {
      backgroundColor: "#08101e",
      titleColor: "#eef4ff",
      bodyColor: "#cbd7ea",
      borderColor: "rgba(255,255,255,0.08)",
      borderWidth: 1,
      displayColors: true,
      padding: 12,
      cornerRadius: 14,
      titleFont: {
        family: "Plus Jakarta Sans",
        size: 12,
        weight: "700",
      },
      bodyFont: {
        family: "Plus Jakarta Sans",
        size: 12,
        weight: "600",
      },
    };
  }

  function destroyChart(key) {
    if (state.charts[key]) {
      state.charts[key].destroy();
      delete state.charts[key];
    }
  }

  function mountChart(key, canvasId, chartConfig) {
    const canvas = byId(canvasId);
    if (!canvas || !window.Chart) return;
    destroyChart(key);
    state.charts[key] = new Chart(canvas.getContext("2d"), chartConfig);
  }

  function registerCenterLabelPlugin() {
    if (!window.Chart) return;
    if (window.__directorNeoCenterLabelRegistered) return;
    window.__directorNeoCenterLabelRegistered = true;
    window.Chart.register({
      id: "neoCenterLabel",
      afterDraw(chart) {
        if (chart.config.type !== "doughnut") return;
        const center = chart.options?.plugins?.neoCenterLabel;
        if (!center) return;
        const meta = chart.getDatasetMeta(0);
        if (!meta?.data?.length) return;
        const point = meta.data[0];
        const ctx = chart.ctx;
        ctx.save();
        ctx.textAlign = "center";
        ctx.fillStyle = COLORS.muted;
        ctx.font = '700 11px "Plus Jakarta Sans", sans-serif';
        ctx.fillText(center.label || "", point.x, point.y - 10);
        ctx.fillStyle = "#eef4ff";
        ctx.font = '900 22px "Plus Jakarta Sans", sans-serif';
        ctx.fillText(center.value || "", point.x, point.y + 18);
        ctx.restore();
      },
    });
  }

  function buildSparklineSvg(series, color) {
    const data = (series || []).map((value) => toNumber(value));
    const width = 220;
    const height = 44;
    const padding = 4;
    if (!data.length || data.every((value) => value === 0)) {
      return `
        <svg class="neo-kpi-sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
          <path class="line" d="M4 ${height - 10} L${width - 4} ${height - 10}" stroke="${color}"></path>
        </svg>
      `;
    }

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    const points = data.map((value, index) => {
      const x = padding + ((width - padding * 2) / Math.max(data.length - 1, 1)) * index;
      const y = height - padding - (((value - min) / range) * (height - padding * 2));
      return [x, y];
    });

    const line = points
      .map((point, index) => `${index === 0 ? "M" : "L"}${point[0].toFixed(2)} ${point[1].toFixed(2)}`)
      .join(" ");
    const fill = `${line} L ${points[points.length - 1][0].toFixed(2)} ${height - padding} L ${points[0][0].toFixed(2)} ${height - padding} Z`;

    return `
      <svg class="neo-kpi-sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
        <path class="fill" d="${fill}" fill="${color}"></path>
        <path class="line" d="${line}" stroke="${color}"></path>
      </svg>
    `;
  }

  function emptyBlock(text) {
    return `<div class="neo-empty">${escapeHtml(text)}</div>`;
  }

  function skeletonList(count = 3) {
    return Array.from({ length: count })
      .map(() => '<div class="neo-skeleton-box" style="min-height:72px;border-radius:16px;"></div>')
      .join("");
  }

  function setSelectOptions(selectId, options, placeholder) {
    const select = byId(selectId);
    if (!select) return;
    select.innerHTML = "";
    if (placeholder !== null) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = placeholder || "Barchasi";
      select.appendChild(option);
    }
    (options || []).forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.name;
      select.appendChild(option);
    });
  }

  function setValue(id, value) {
    const node = byId(id);
    if (node) node.value = value || "";
  }

  function currentSearchParams() {
    return new URLSearchParams(window.location.search);
  }

  function buildApiUrl() {
    const url = new URL(API_URL, window.location.origin);
    currentSearchParams().forEach((value, key) => url.searchParams.set(key, value));
    url.searchParams.set("_", `${Date.now()}`);
    return url.toString();
  }

  function toggleCustomDates() {
    const preset = byId("periodPreset")?.value || "this_month";
    const isCustom = preset === "custom";
    ["periodFromWrap", "periodToWrap"].forEach((id) => {
      const node = byId(id);
      if (node) node.classList.toggle("neo-hidden", !isCustom);
    });
  }

  function syncFilterControls(payload) {
    const options = payload.filters?.options || {};
    const applied = payload.filters?.applied || {};

    setSelectOptions("periodPreset", PRESETS, null);
    setSelectOptions("branchSelect", options.branches || [], "Barchasi");
    setSelectOptions("teacherSelect", options.teachers || [], "Barchasi");
    setSelectOptions("groupSelect", options.groups || [], "Barchasi");
    setSelectOptions("categorySelect", options.categories || [], "Barchasi");

    setValue("periodPreset", applied.preset || "this_month");
    setValue("periodFrom", applied.date_from || "");
    setValue("periodTo", applied.date_to || "");
    setValue("branchSelect", (applied.branch_ids || [])[0] || "");
    setValue("teacherSelect", (applied.teacher_ids || [])[0] || "");
    setValue("groupSelect", (applied.group_ids || [])[0] || "");
    setValue("categorySelect", (applied.category_ids || [])[0] || "");
    toggleCustomDates();
  }

  function applyFiltersToUrl() {
    const params = currentSearchParams();
    FILTER_KEYS.forEach((key) => params.delete(key));

    const values = {
      preset: byId("periodPreset")?.value || "",
      date_from: byId("periodFrom")?.value || "",
      date_to: byId("periodTo")?.value || "",
      branch: byId("branchSelect")?.value || "",
      teacher: byId("teacherSelect")?.value || "",
      group: byId("groupSelect")?.value || "",
      category: byId("categorySelect")?.value || "",
    };

    if (values.preset) params.set("preset", values.preset);
    if (values.preset === "custom") {
      if (values.date_from) params.set("date_from", values.date_from);
      if (values.date_to) params.set("date_to", values.date_to);
    }

    ["branch", "teacher", "group", "category"].forEach((key) => {
      if (values[key]) params.set(key, values[key]);
    });

    const url = new URL(window.location.href);
    url.search = params.toString();
    window.history.replaceState({}, "", url.toString());
  }

  function showError(message) {
    const box = byId("dashboardErrorBox");
    const text = byId("dashboardErrorText");
    if (text) text.textContent = message || "Dashboard yuklanmadi.";
    if (box) box.classList.remove("neo-hidden");
  }

  function hideError() {
    byId("dashboardErrorBox")?.classList.add("neo-hidden");
  }

  function renderLoading() {
    const kpi = byId("executiveKpis");
    if (kpi) {
      kpi.innerHTML = Array.from({ length: 6 }).map(() => '<div class="neo-kpi-skeleton"></div>').join("");
    }

    [
      "financeMiniStats",
      "paymentsLegend",
      "leadFunnel",
      "channelList",
      "teacherList",
      "alertsList",
      "insightsList",
      "targetsList",
      "groupHealthCards",
    ].forEach((id) => {
      const node = byId(id);
      if (node) node.innerHTML = skeletonList(id === "targetsList" ? 3 : 3);
    });

    const riskTable = byId("riskStudentsTable");
    if (riskTable) {
      riskTable.innerHTML = `<tr><td colspan="3">${emptyBlock("Yuklanmoqda...")}</td></tr>`;
    }

    const groupsTable = byId("groupsTable");
    if (groupsTable) {
      groupsTable.innerHTML = `<tr><td colspan="4">${emptyBlock("Yuklanmoqda...")}</td></tr>`;
    }
  }

  function renderHeader(payload) {
    const trend = payload.executive?.trend_signal || {};
    const system = payload.system || {};
    const rangeText = `${formatDate(system.start_date)} - ${formatDate(system.end_date)}`;
    const updatedText = system.last_updated || "--:--:--";

    if (byId("heroRangeText")) byId("heroRangeText").textContent = rangeText;
    if (byId("heroUpdatedText")) byId("heroUpdatedText").textContent = updatedText;
    if (byId("heroTrendText")) byId("heroTrendText").textContent = trend.title || "Asosiy signal yuklanmoqda...";
  }

  function createKpiCard(item) {
    return `
      <article class="neo-kpi-card">
        <div class="neo-kpi-top">
          <div class="neo-kpi-title">
            <i class="fa-solid ${escapeHtml(item.icon)}"></i>
            <span>${escapeHtml(item.title)}</span>
          </div>
          <span class="neo-kpi-delta ${escapeHtml(item.deltaClass)}">${escapeHtml(item.deltaText)}</span>
        </div>
        <div class="neo-kpi-value">${escapeHtml(item.value)}</div>
        <div class="neo-kpi-bottom">
          <div class="neo-kpi-sub">${escapeHtml(item.note)}</div>
          ${buildSparklineSvg(item.series, item.color)}
        </div>
      </article>
    `;
  }

  function renderKpis(payload) {
    const finance = payload.finance || {};
    const students = payload.students || {};
    const marketing = payload.marketing || {};
    const charts = payload.charts || {};
    const container = byId("executiveKpis");
    if (!container) return;

    const cards = [
      {
        title: "Daromad",
        value: formatCompactMoney(finance.income || 0),
        deltaText: formatSignedPercent(finance.income_growth || 0),
        deltaClass: deltaClass(finance.income_growth || 0),
        note: "Joriy tushum",
        icon: "fa-sack-dollar",
        series: charts.income || [],
        color: COLORS.cyan,
      },
      {
        title: "Foyda",
        value: formatCompactMoney(finance.profit || 0),
        deltaText: `Marja ${formatPercent(finance.profit_margin || 0)}`,
        deltaClass: toNumber(finance.profit || 0) >= 0 ? "up" : "down",
        note: "Sof foyda",
        icon: "fa-chart-line",
        series: charts.cashflow || [],
        color: COLORS.green,
      },
      {
        title: "Xarajat",
        value: formatCompactMoney(finance.expense || 0),
        deltaText: formatCompactMoney(finance.teacher_shares || 0),
        deltaClass: "",
        note: "Jami xarajat",
        icon: "fa-wallet",
        series: charts.expenses || [],
        color: COLORS.red,
      },
      {
        title: "Qarz",
        value: formatCompactMoney(finance.open_debt || 0),
        deltaText: formatPercent(finance.debt_ratio || 0),
        deltaClass: toNumber(finance.open_debt || 0) > 0 ? "down" : "up",
        note: "Ochiq qarz",
        icon: "fa-triangle-exclamation",
        series: charts.debt_series || [],
        color: COLORS.amber,
      },
      {
        title: "Faol o'quvchi",
        value: formatNumber(students.active_students || 0),
        deltaText: formatSignedPercent(students.growth_pct || 0),
        deltaClass: deltaClass(students.growth_pct || 0),
        note: "Joriy holat",
        icon: "fa-user-graduate",
        series: charts.income_students || [],
        color: COLORS.violet,
      },
      {
        title: "Konversiya",
        value: formatPercent(marketing.conversion_rate || 0),
        deltaText: `${formatNumber(marketing.paid_students || 0)} ta`,
        deltaClass: "",
        note: "Lead to'lovga o'tdi",
        icon: "fa-filter-circle-dollar",
        series: charts.new_students || [],
        color: COLORS.blue,
      },
    ];

    container.innerHTML = cards.map(createKpiCard).join("");
  }

  function renderFinance(payload) {
    const finance = payload.finance || {};
    const charts = payload.charts || {};

    const miniStats = byId("financeMiniStats");
    if (miniStats) {
      const items = [
        { title: "O'rtacha to'lov", value: formatCompactMoney(finance.avg_payment || 0), note: "Bitta to'lov" },
        { title: "To'lov bajarildi", value: formatPercent(finance.payment_completion_rate || 0), note: `${formatNumber(finance.paid_students_count || 0)} / ${formatNumber(finance.billed_students_count || 0)} talaba` },
        { title: "Daromad sifati", value: formatPercent(finance.income_quality_score || 0), note: "Sifat bahosi" },
        { title: "Qayta to'lov", value: formatPercent(finance.recurring_share || 0), note: "Takror to'lov ulushi" },
      ];

      miniStats.innerHTML = items.map((item) => `
        <article class="neo-mini-stat">
          <div class="neo-mini-stat-head">
            <span class="neo-label">${escapeHtml(item.title)}</span>
          </div>
          <div class="neo-mini-stat-value">${escapeHtml(item.value)}</div>
          <small>${escapeHtml(item.note)}</small>
        </article>
      `).join("");
    }

    mountChart("financeMain", "financeMainChart", {
      type: "line",
      data: {
        labels: charts.labels || [],
        datasets: [
          {
            label: "Daromad",
            data: charts.income || [],
            borderColor: COLORS.cyan,
            backgroundColor: "rgba(62, 200, 255, 0.18)",
            fill: true,
            tension: 0.35,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
          {
            label: "Xarajat",
            data: charts.expenses || [],
            borderColor: COLORS.red,
            backgroundColor: "rgba(255, 93, 115, 0.12)",
            tension: 0.35,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
          {
            label: "Pul oqimi",
            data: charts.cashflow || [],
            borderColor: COLORS.green,
            backgroundColor: "rgba(41, 211, 145, 0.12)",
            tension: 0.35,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
          {
            label: "Qarz",
            data: charts.debt_series || [],
            borderColor: COLORS.amber,
            borderDash: [6, 6],
            tension: 0.25,
            pointRadius: 2,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            labels: {
              color: COLORS.muted,
              usePointStyle: true,
              boxWidth: 10,
            },
          },
          tooltip: chartTooltip(),
        },
        scales: {
          x: {
            ticks: { color: COLORS.muted },
            grid: { color: COLORS.grid },
          },
          y: {
            ticks: {
              color: COLORS.muted,
              callback(value) {
                return formatCompactMoney(value);
              },
            },
            grid: { color: COLORS.grid },
          },
        },
      },
    });
  }

  function renderPayments(payload) {
    const finance = payload.finance || {};
    const rows = finance.breakdown?.by_type || [];
    const legend = byId("paymentsLegend");
    const completionRate = toNumber(finance.payment_completion_rate || 0);
    const paidCount = toNumber(finance.paid_students_count || 0);
    const billedCount = toNumber(finance.billed_students_count || 0);
    const centerText = `${Math.round(completionRate)}%`;
    const colors = [COLORS.cyan, COLORS.violet, COLORS.green, COLORS.amber];
    const total = rows.reduce((sum, row) => sum + toNumber(row.value), 0);

    if (byId("paymentCompletionText")) byId("paymentCompletionText").textContent = centerText;
    if (byId("paymentProgressText")) byId("paymentProgressText").textContent = centerText;
    if (byId("paymentProgressFill")) byId("paymentProgressFill").style.width = `${Math.max(0, Math.min(completionRate, 100))}%`;
    if (byId("paymentsMeta")) {
      byId("paymentsMeta").textContent = `${paidCount} / ${billedCount} talaba to'lagan · Ochiq qarz ${formatCompactMoney(finance.open_debt || 0)}`;
    }

    if (legend) {
      legend.innerHTML = rows.length
        ? rows.map((row, index) => {
            const share = total ? ((toNumber(row.value) / total) * 100).toFixed(1) : "0.0";
            return `
              <article class="neo-list-item">
                <div class="neo-legend-item">
                  <div class="neo-legend-left">
                    <span class="neo-dot" style="--color:${colors[index % colors.length]}"></span>
                    <label>${escapeHtml(row.name || "Noma'lum")}</label>
                  </div>
                  <span class="neo-badge info">${escapeHtml(share)}%</span>
                </div>
                <p>${escapeHtml(formatCompactMoney(row.value || 0))}</p>
              </article>
            `;
          }).join("")
        : emptyBlock("To'lov ma'lumoti yo'q");
    }

    mountChart("paymentsDonut", "paymentsDonutChart", {
      type: "doughnut",
      data: {
        labels: rows.map((row) => row.name || "Noma'lum"),
        datasets: [
          {
            data: rows.map((row) => toNumber(row.value)),
            backgroundColor: rows.map((_, index) => colors[index % colors.length]),
            borderColor: "#08101e",
            borderWidth: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "70%",
        plugins: {
          legend: { display: false },
          tooltip: chartTooltip(),
          neoCenterLabel: {
            label: "To'lov",
            value: centerText,
          },
        },
      },
    });
  }

  function renderMarketing(payload) {
    const marketing = payload.marketing || {};
    const funnel = marketing.funnel || [];
    const sources = (marketing.sources || []).slice(0, 5);
    const funnelNode = byId("leadFunnel");
    const channelNode = byId("channelList");
    const maxCount = Math.max(...funnel.map((item) => toNumber(item.count)), 1);

    if (funnelNode) {
      funnelNode.innerHTML = funnel.length
        ? funnel.map((item) => {
            const fill = `${Math.max((toNumber(item.count) / maxCount) * 100, 14)}%`;
            return `
              <div class="neo-funnel-stage">
                <label>${escapeHtml(item.stage)}</label>
                <div class="neo-funnel-bar" style="--fill:${fill}">
                  <span></span>
                </div>
                <div class="neo-funnel-value">${escapeHtml(formatNumber(item.count || 0))}</div>
              </div>
            `;
          }).join("")
        : emptyBlock("Lead yo'q");
    }

    if (channelNode) {
      channelNode.innerHTML = sources.length
        ? sources.map((item, index) => `
            <article class="neo-list-item">
              <div class="neo-list-item-head">
                <strong>${escapeHtml(item.name || "Noma'lum")}</strong>
                <span class="neo-badge ${item.source_efficiency_score >= 60 ? "good" : item.source_efficiency_score >= 35 ? "warn" : "bad"}">${escapeHtml(formatPercent(item.conversion || 0))}</span>
              </div>
              <p>${escapeHtml(formatNumber(item.count || 0))} ta lead · ${escapeHtml(formatCompactMoney(item.revenue || 0))}</p>
            </article>
          `).join("")
        : emptyBlock("Marketing manbasi yo'q");
    }
  }

  function renderTeachers(payload) {
    const rows = (payload.teachers?.ranking || []).slice(0, 4);
    const node = byId("teacherList");
    if (!node) return;
    node.innerHTML = rows.length
      ? rows.map((item, index) => `
          <article class="neo-list-item">
            <div class="neo-list-item-head">
              <div>
                <strong>${index + 1}. ${escapeHtml(item.teacher_name)}</strong>
                <p>${escapeHtml(formatNumber(item.students || 0))} o'quvchi · ${escapeHtml(formatNumber(item.groups || 0))} guruh</p>
              </div>
              <span class="neo-badge good">${escapeHtml(formatCompactMoney(item.revenue || 0))}</span>
            </div>
            <div class="neo-chip-row">
              <span class="neo-chip">Holat: <strong>${escapeHtml(formatPercent(item.health_score || 0))}</strong></span>
              <span class="neo-chip">Davomat: <strong>${escapeHtml(item.attendance_rate === null ? "--" : formatPercent(item.attendance_rate || 0))}</strong></span>
              <span class="neo-chip">Saqlash: <strong>${escapeHtml(formatPercent(item.retention_rate || 0))}</strong></span>
            </div>
          </article>
        `).join("")
      : emptyBlock("Ustoz topilmadi");
  }

  function renderRiskStudents(payload) {
    const rows = (payload.students?.risk_students || []).slice(0, 6);
    const node = byId("riskStudentsTable");
    if (!node) return;
    if (!rows.length) {
      node.innerHTML = `<tr><td colspan="3">${emptyBlock("Xavf yo'q")}</td></tr>`;
      return;
    }

    node.innerHTML = rows.map((item) => `
      <tr>
        <td>
          <strong>${escapeHtml(item.name)}</strong>
          <span class="neo-table-note">${escapeHtml(item.course || "Guruhsiz")}</span>
        </td>
        <td>
          ${escapeHtml(item.reason || "—")}
          <span class="neo-table-note">Risk: ${escapeHtml(formatPercent(item.risk_score || 0))}</span>
        </td>
        <td>${escapeHtml(formatCompactMoney(item.debt || 0))}</td>
      </tr>
    `).join("");
  }

  function renderGroups(payload) {
    const groups = (payload.groups?.profitability || []).slice(0, 5);
    const summary = payload.groups?.health_summary || {};
    const table = byId("groupsTable");
    const cards = byId("groupHealthCards");

    if (table) {
      table.innerHTML = groups.length
        ? groups.map((item) => `
            <tr>
              <td>
                <strong>${escapeHtml(item.group_name)}</strong>
                <span class="neo-table-note">${escapeHtml(item.teacher_name || "Ustoz yo'q")}</span>
              </td>
              <td>${escapeHtml(formatCompactMoney(item.revenue || 0))}</td>
              <td>${escapeHtml(formatCompactMoney(item.open_debt || 0))}</td>
              <td><span class="neo-badge ${toneClass(item.health_label)}">${escapeHtml(item.health_label === "Strong" ? "Yaxshi" : item.health_label === "Stable" ? "Barqaror" : item.health_label === "Risky" ? "Xavf" : item.health_label === "Weak" ? "Zaif" : "Yopish")}</span></td>
            </tr>
          `).join("")
        : `<tr><td colspan="4">${emptyBlock("Guruh topilmadi")}</td></tr>`;
    }

    if (cards) {
      const all = toNumber(summary.strong) + toNumber(summary.stable) + toNumber(summary.risky) + toNumber(summary.weak) + toNumber(summary.close_candidate);
      const items = [
        { title: "Yaxshi", count: toNumber(summary.strong) + toNumber(summary.stable), tone: "good" },
        { title: "Xavf", count: toNumber(summary.risky) + toNumber(summary.weak), tone: "warn" },
        { title: "Yopish", count: toNumber(summary.close_candidate), tone: "bad" },
      ];
      cards.innerHTML = items.map((item) => `
        <article class="neo-health-card">
          <span class="neo-label">${escapeHtml(item.title)}</span>
          <strong>${escapeHtml(formatNumber(item.count))}</strong>
          <p>${escapeHtml(all ? formatPercent((item.count / all) * 100) : "0%")}</p>
          <div class="neo-progress-track">
            <span style="width:${all ? Math.min((item.count / all) * 100, 100) : 0}%;background:${item.tone === "good" ? COLORS.green : item.tone === "warn" ? COLORS.amber : COLORS.red};"></span>
          </div>
        </article>
      `).join("");
    }
  }

  function renderTargets(payload) {
    const plans = payload.plans || {};
    const node = byId("targetsList");
    if (!node) return;
    const items = [
      { title: "Daromad rejasi", data: plans.finance || {}, color: COLORS.cyan },
      { title: "O'quvchi rejasi", data: plans.students || {}, color: COLORS.green },
      { title: "Lead rejasi", data: plans.marketing || {}, color: COLORS.amber },
    ];

    node.innerHTML = items.map((item) => {
      const percentValue = Math.max(0, Math.min(toNumber(item.data.pct || 0), 100));
      return `
        <article class="neo-target-card">
          <div class="neo-target-head">
            <strong>${escapeHtml(item.title)}</strong>
            <span class="neo-badge info">${escapeHtml(item.data.mode === "configured" ? "Qo'lda" : "Hisob" )}</span>
          </div>
          <strong>${escapeHtml(formatNumber(item.data.current || 0))} / ${escapeHtml(formatNumber(item.data.target || 0))}</strong>
          <p>${escapeHtml(formatNumber(item.data.rem || 0))} qoldi</p>
          <div class="neo-progress-track">
            <span style="width:${percentValue}%;background:${item.color};"></span>
          </div>
        </article>
      `;
    }).join("");

    mountChart("growthMini", "growthMiniChart", {
      type: "line",
      data: {
        labels: payload.charts?.labels || [],
        datasets: [
          {
            label: "Yangi o'quvchi",
            data: payload.charts?.new_students || [],
            borderColor: COLORS.blue,
            backgroundColor: "rgba(93, 125, 255, 0.16)",
            fill: true,
            tension: 0.35,
          },
          {
            label: "To'lov qilgan",
            data: payload.charts?.income_students || [],
            borderColor: COLORS.cyan,
            backgroundColor: "rgba(62, 200, 255, 0.12)",
            tension: 0.35,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: {
              color: COLORS.muted,
              usePointStyle: true,
            },
          },
          tooltip: chartTooltip(),
        },
        scales: {
          x: {
            ticks: { color: COLORS.muted },
            grid: { color: COLORS.grid },
          },
          y: {
            ticks: { color: COLORS.muted },
            grid: { color: COLORS.grid },
          },
        },
      },
    });
  }

  function buildAlerts(payload) {
    const alerts = [];
    const hub = payload.executive?.problem_hub || [];
    const closeCandidate = (payload.groups?.close_candidates || [])[0];
    const riskyTeacher = (payload.teachers?.at_risk || [])[0];

    hub.forEach((item) => {
      alerts.push({
        title: item.label || "Signal",
        text: `${formatNumber(item.value || 0)} ta · ${item.detail_kind === "money" ? formatCompactMoney(item.detail || 0) : formatNumber(item.detail || 0)}`,
        tone: item.tone || "info",
      });
    });

    if (closeCandidate) {
      alerts.push({
        title: `${closeCandidate.group_name} xavfda`,
        text: `${closeCandidate.primary_action} · Holat ${formatPercent(closeCandidate.health_score || 0)}`,
        tone: "warning",
      });
    }

    if (riskyTeacher) {
      alerts.push({
        title: `${riskyTeacher.teacher_name} nazoratda`,
        text: `Davomat ${riskyTeacher.attendance_rate === null ? "--" : formatPercent(riskyTeacher.attendance_rate || 0)} · Qarz ${formatPercent(riskyTeacher.debt_ratio || 0)}`,
        tone: "info",
      });
    }

    return alerts.slice(0, 5);
  }

  function renderAlerts(payload) {
    const node = byId("alertsList");
    if (!node) return;
    const alerts = buildAlerts(payload);
    node.innerHTML = alerts.length
      ? alerts.map((item) => `
          <article class="neo-list-item">
            <div class="neo-list-item-head">
              <strong>${escapeHtml(item.title)}</strong>
              <span class="neo-badge ${toneClass(item.tone)}">${escapeHtml(item.tone === "danger" ? "Jiddiy" : item.tone === "warning" ? "Ogoh" : "Signal")}</span>
            </div>
            <p>${escapeHtml(item.text)}</p>
          </article>
        `).join("")
      : emptyBlock("Signal yo'q");
  }

  function renderInsights(payload) {
    const trend = payload.executive?.trend_signal || {};
    const insights = (payload.insights || []).slice(0, 4);
    const trendNode = byId("trendSignalCard");
    const listNode = byId("insightsList");

    if (trendNode) {
      const chips = (trend.chips || [])
        .slice(0, 3)
        .map((chip) => `<span class="neo-chip">${escapeHtml(chip.label)}: <strong>${escapeHtml(chip.kind === "money" ? formatCompactMoney(chip.value) : chip.kind === "pct" || chip.kind === "pct_signed" ? formatPercent(chip.value) : formatNumber(chip.value))}</strong></span>`)
        .join("");

      trendNode.innerHTML = `
        <span class="neo-label">Asosiy signal</span>
        <h4>${escapeHtml(trend.title || "Signal yo'q")}</h4>
        <p>${escapeHtml(trend.text || "Hozircha tavsiya yo'q")}</p>
        <div class="neo-chip-row">${chips}</div>
      `;
    }

    if (listNode) {
      listNode.innerHTML = insights.length
        ? insights.map((item) => `
            <article class="neo-list-item">
              <div class="neo-list-item-head">
                <strong>${escapeHtml(item.title)}</strong>
                <span class="neo-badge ${toneClass(item.severity)}">${escapeHtml(item.severity === "critical" ? "Jiddiy" : item.severity === "high" ? "Yuqori" : item.severity === "medium" ? "O'rta" : "Past")}</span>
              </div>
              <p>${escapeHtml(item.text || "")}</p>
            </article>
          `).join("")
        : emptyBlock("Xulosa yo'q");
    }
  }

  function renderAll(payload) {
    renderHeader(payload);
    syncFilterControls(payload);
    renderKpis(payload);
    renderFinance(payload);
    renderPayments(payload);
    renderMarketing(payload);
    renderTeachers(payload);
    renderRiskStudents(payload);
    renderGroups(payload);
    renderTargets(payload);
    renderAlerts(payload);
    renderInsights(payload);
  }

  function csvEscape(value) {
    return `"${String(value ?? "").replace(/"/g, '""')}"`;
  }

  function exportCurrentCsv() {
    if (!state.payload) return;
    const payload = state.payload;
    const lines = [];
    lines.push(["Bo'lim", "Nom", "Qiymat", "Izoh"].map(csvEscape).join(","));

    lines.push(["KPI", "Daromad", payload.finance?.income || 0, "Joriy tushum"].map(csvEscape).join(","));
    lines.push(["KPI", "Foyda", payload.finance?.profit || 0, "Sof foyda"].map(csvEscape).join(","));
    lines.push(["KPI", "Xarajat", payload.finance?.expense || 0, "Jami xarajat"].map(csvEscape).join(","));
    lines.push(["KPI", "Qarz", payload.finance?.open_debt || 0, "Ochiq qarz"].map(csvEscape).join(","));
    lines.push(["KPI", "Faol o'quvchi", payload.students?.active_students || 0, "Joriy holat"].map(csvEscape).join(","));
    lines.push(["KPI", "Konversiya", payload.marketing?.conversion_rate || 0, "Lead to'lovga o'tdi"].map(csvEscape).join(","));

    (payload.teachers?.ranking || []).slice(0, 5).forEach((item) => {
      lines.push(["Ustoz", item.teacher_name, item.revenue || 0, `${item.students || 0} o'quvchi`].map(csvEscape).join(","));
    });

    (payload.groups?.profitability || []).slice(0, 5).forEach((item) => {
      lines.push(["Guruh", item.group_name, item.revenue || 0, item.health_label || ""].map(csvEscape).join(","));
    });

    (payload.students?.risk_students || []).slice(0, 5).forEach((item) => {
      lines.push(["Xavf", item.name, item.debt || 0, item.reason || ""].map(csvEscape).join(","));
    });

    const blob = new Blob([`\uFEFF${lines.join("\n")}`], { type: "text/csv;charset=utf-8;" });
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = "direktor-panel.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(href);
  }

  async function loadDashboard() {
    if (state.loading) return;
    state.loading = true;
    hideError();
    renderLoading();

    try {
      const response = await fetch(buildApiUrl(), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) {
        throw new Error(`Dashboard yuklanmadi: ${response.status}`);
      }
      const payload = await response.json();
      state.payload = payload;
      renderAll(payload);
    } catch (error) {
      showError(error.message || "Dashboard yuklanmadi.");
    } finally {
      state.loading = false;
    }
  }

  function bindEvents() {
    byId("periodPreset")?.addEventListener("change", () => {
      if (byId("periodPreset")?.value !== "custom") {
        setValue("periodFrom", "");
        setValue("periodTo", "");
      }
      toggleCustomDates();
    });

    byId("refreshDashboardBtn")?.addEventListener("click", () => {
      applyFiltersToUrl();
      loadDashboard();
    });

    byId("retryDashboardBtn")?.addEventListener("click", loadDashboard);
    byId("exportCsvBtn")?.addEventListener("click", exportCurrentCsv);
  }

  document.addEventListener("DOMContentLoaded", () => {
    registerCenterLabelPlugin();
    if (window.Chart) {
      window.Chart.defaults.color = COLORS.muted;
      window.Chart.defaults.font.family = "Plus Jakarta Sans";
    }
    bindEvents();
    toggleCustomDates();
    loadDashboard();
  });
})();
