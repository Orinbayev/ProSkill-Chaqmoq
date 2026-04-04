(function () {
  const config = window.directorDashboardConfig || {};
  const DASHBOARD_API_URL = config.apiUrl || "";
  const PREVIEW_LIMIT = 3;
  const TEACHER_CHART_LIMIT = 5;
  const DRAWER_PAGE_SIZE = 6;

  const dashboardState = {
    data: null,
    charts: {},
    drawer: {
      type: null,
      page: 1,
      query: "",
    },
  };

  const LABELS = {
    health: {
      Strong: "Kuchli",
      Stable: "Barqaror",
      Risky: "Xavfli",
      Weak: "Sust",
      "Close Candidate": "Yopish nomzodi",
    },
    action: {
      grow: "O'sish",
      fix: "Tuzatish",
      monitor: "Kuzatish",
      stop: "Yopish",
    },
    severity: {
      low: "Past",
      medium: "O'rta",
      high: "Yuqori",
      critical: "Jiddiy",
    },
  };

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatInteger(value) {
    return new Intl.NumberFormat("uz-UZ").format(Math.round(Number(value || 0)));
  }

  function fmtMoney(value) {
    const num = Number(value || 0);
    const prefix = num < 0 ? "-" : "";
    return `${prefix}${new Intl.NumberFormat("uz-UZ").format(Math.abs(Math.round(num)))} so'm`;
  }

  function fmtCompact(value) {
    const num = Number(value || 0);
    const abs = Math.abs(num);
    const prefix = num < 0 ? "-" : "";
    if (abs >= 1e9) return `${prefix}${(abs / 1e9).toFixed(1)} mlrd`;
    if (abs >= 1e6) return `${prefix}${(abs / 1e6).toFixed(1)} mln`;
    if (abs >= 1e3) return `${prefix}${Math.round(abs / 1e3)} ming`;
    return `${prefix}${Math.round(abs)}`;
  }

  function fmtCompactMoney(value) {
    return `${fmtCompact(value)} so'm`;
  }

  function fmtSignedPct(value) {
    if (value === null || value === undefined || value === "") return "—";
    const num = Number(value || 0);
    if (num > 0) return `+${num}%`;
    return `${num}%`;
  }

  function displayPct(value) {
    if (value === null || value === undefined || value === "") return "Ma'lumot yo'q";
    return `${value}%`;
  }

  function formatMetricValue(value, kind) {
    if (value === null || value === undefined || value === "") {
      return kind === "money" ? fmtMoney(0) : "—";
    }
    switch (kind) {
      case "money":
        return fmtMoney(value);
      case "money_compact":
        return fmtCompactMoney(value);
      case "pct":
        return displayPct(value);
      case "pct_signed":
        return fmtSignedPct(value);
      case "number":
      default:
        return formatInteger(value);
    }
  }

  function toneClass(value) {
    return String(value || "info").toLowerCase();
  }

  function trendClass(value) {
    const num = Number(value || 0);
    if (num > 0) return "up";
    if (num < 0) return "down";
    return "flat";
  }

  function labelHealth(value) {
    return LABELS.health[value] || value || "Noma'lum";
  }

  function labelAction(value) {
    return LABELS.action[value] || value || "Kuzatish";
  }

  function labelSeverity(value) {
    return LABELS.severity[value] || value || "Past";
  }

  function slugUz(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/'/g, "")
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-]/g, "");
  }

  function formatDate(isoDate) {
    if (!isoDate) return "—";
    const date = new Date(`${isoDate}T00:00:00`);
    if (Number.isNaN(date.getTime())) return isoDate;
    return new Intl.DateTimeFormat("uz-UZ", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    }).format(date);
  }

  function premiumTooltip(callbacks = {}) {
    return {
      backgroundColor: "#08111f",
      titleColor: "#f8fafc",
      bodyColor: "#dce7f3",
      borderColor: "rgba(148,163,184,0.16)",
      borderWidth: 1,
      cornerRadius: 14,
      padding: 12,
      displayColors: false,
      titleMarginBottom: 6,
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
      callbacks,
    };
  }

  if (window.Chart) {
    Chart.register({
      id: "directorDashboardCenterLabel",
      afterDraw(chart) {
        if (chart.config.type !== "doughnut") return;
        const centerLabel = chart.options?.plugins?.centerLabel;
        if (!centerLabel) return;
        const meta = chart.getDatasetMeta(0);
        if (!meta?.data?.length) return;
        const point = meta.data[0];
        const x = point.x;
        const y = point.y;
        const ctx = chart.ctx;
        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "rgba(141, 162, 188, 0.82)";
        ctx.font = '600 11px "Plus Jakarta Sans", sans-serif';
        ctx.fillText(centerLabel.label || "", x, y - 10);
        ctx.fillStyle = "#f8fafc";
        ctx.font = '800 16px "Plus Jakarta Sans", sans-serif';
        ctx.fillText(centerLabel.value || "", x, y + 12);
        ctx.restore();
      },
    });
  }

  function getSearchParams() {
    return new URLSearchParams(window.location.search);
  }

  function setSearchParams(params) {
    const url = new URL(window.location.href);
    url.search = params.toString();
    window.history.replaceState({}, "", url.toString());
  }

  function preserveFilterHref(baseHref) {
    const url = new URL(baseHref, window.location.origin);
    const params = getSearchParams();
    [
      "date_from",
      "date_to",
      "preset",
      "branch",
      "category",
      "group",
      "teacher",
      "payment_type",
      "source",
      "student_cycle",
      "student_status",
      "debt_status",
    ].forEach((key) => {
      if (params.has(key)) {
        url.searchParams.set(key, params.get(key));
      }
    });
    return `${url.pathname}${url.search}`;
  }

  function syncPreserveLinks() {
    document.querySelectorAll(".preserve-link").forEach((link) => {
      const baseHref = link.dataset.baseHref || link.getAttribute("href");
      if (!baseHref) return;
      link.setAttribute("href", preserveFilterHref(baseHref));
    });
  }

  function fillSelect(selectId, options, placeholder) {
    const select = document.getElementById(selectId);
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

  function bindToolbar() {
    const applyButton = document.getElementById("applyFiltersBtn");
    const resetButton = document.getElementById("resetFiltersBtn");
    const presetSelect = document.getElementById("filterPreset");
    if (applyButton) applyButton.addEventListener("click", applyFilters);
    if (resetButton) resetButton.addEventListener("click", resetFilters);
    if (presetSelect) presetSelect.addEventListener("change", toggleCustomDates);
  }

  function bindInteractionDelegation() {
    document.addEventListener("click", (event) => {
      const openTrigger = event.target.closest("[data-open-drawer]");
      if (openTrigger) {
        event.preventDefault();
        openDrawer(openTrigger.dataset.openDrawer);
        return;
      }

      if (event.target.closest("#drawerBackdrop") || event.target.closest("#drawerCloseBtn")) {
        closeDrawer();
      }
    });
  }

  function bindDrawer() {
    const search = document.getElementById("drawerSearch");
    const prev = document.getElementById("drawerPrev");
    const next = document.getElementById("drawerNext");

    if (search) {
      search.addEventListener("input", (event) => {
        dashboardState.drawer.query = event.target.value || "";
        dashboardState.drawer.page = 1;
        renderDrawer();
      });
    }

    if (prev) {
      prev.addEventListener("click", () => {
        if (dashboardState.drawer.page > 1) {
          dashboardState.drawer.page -= 1;
          renderDrawer();
        }
      });
    }

    if (next) {
      next.addEventListener("click", () => {
        const drawerData = getDrawerDataset();
        if (dashboardState.drawer.page < drawerData.totalPages) {
          dashboardState.drawer.page += 1;
          renderDrawer();
        }
      });
    }
  }

  function toggleCustomDates() {
    const preset = document.getElementById("filterPreset")?.value;
    const fromInput = document.getElementById("filterDateFrom");
    const toInput = document.getElementById("filterDateTo");
    const custom = preset === "custom";
    if (fromInput) fromInput.disabled = !custom;
    if (toInput) toInput.disabled = !custom;
  }

  function hydrateFilterOptions(filters) {
    if (!filters) return;
    const options = filters.options || {};
    const applied = filters.applied || {};

    fillSelect("filterPreset", [
      { id: "today", name: "Bugun" },
      { id: "yesterday", name: "Kecha" },
      { id: "this_week", name: "Bu hafta" },
      { id: "this_month", name: "Bu oy" },
      { id: "last_month", name: "O'tgan oy" },
      { id: "this_quarter", name: "Bu chorak" },
      { id: "custom", name: "Ixtiyoriy sana oralig'i" },
    ], null);
    fillSelect("filterBranch", options.branches || [], "Barchasi");
    fillSelect("filterCategory", options.categories || [], "Barchasi");
    fillSelect("filterGroup", options.groups || [], "Barchasi");
    fillSelect("filterTeacher", options.teachers || [], "Barchasi");
    fillSelect("filterPaymentType", options.payment_types || [], "Barchasi");
    fillSelect("filterSource", options.sources || [], "Barchasi");
    fillSelect("filterStudentCycle", options.student_cycles || [], "Barchasi");
    fillSelect("filterStudentStatus", options.student_statuses || [], "Barchasi");
    fillSelect("filterDebtStatus", options.debt_statuses || [], "Barchasi");

    setControlValue("filterPreset", applied.preset || "this_month");
    setControlValue("filterDateFrom", applied.date_from || "");
    setControlValue("filterDateTo", applied.date_to || "");
    setControlValue("filterBranch", (applied.branch_ids || [])[0] || "");
    setControlValue("filterCategory", (applied.category_ids || [])[0] || "");
    setControlValue("filterGroup", (applied.group_ids || [])[0] || "");
    setControlValue("filterTeacher", (applied.teacher_ids || [])[0] || "");
    setControlValue("filterPaymentType", (applied.payment_types || [])[0] || "");
    setControlValue("filterSource", (applied.source_ids || [])[0] || "");
    setControlValue("filterStudentCycle", applied.student_cycle || "");
    setControlValue("filterStudentStatus", applied.student_status || "");
    setControlValue("filterDebtStatus", applied.debt_status || "");
    toggleCustomDates();
  }

  function setControlValue(controlId, value) {
    const element = document.getElementById(controlId);
    if (!element) return;
    element.value = value ?? "";
  }

  function readControlValue(controlId) {
    const element = document.getElementById(controlId);
    if (!element) return "";
    return String(element.value || "").trim();
  }

  function applyFilters() {
    const params = new URLSearchParams();
    const preset = readControlValue("filterPreset") || "this_month";
    const dateFrom = readControlValue("filterDateFrom");
    const dateTo = readControlValue("filterDateTo");

    if (preset === "custom" && (!dateFrom || !dateTo || dateFrom > dateTo)) {
      window.alert("Ixtiyoriy sana oralig'i uchun to'g'ri sanalarni tanlang.");
      return;
    }

    params.set("preset", preset);
    if (preset === "custom") {
      params.set("date_from", dateFrom);
      params.set("date_to", dateTo);
    }

    [
      ["branch", readControlValue("filterBranch")],
      ["category", readControlValue("filterCategory")],
      ["group", readControlValue("filterGroup")],
      ["teacher", readControlValue("filterTeacher")],
      ["payment_type", readControlValue("filterPaymentType")],
      ["source", readControlValue("filterSource")],
      ["student_cycle", readControlValue("filterStudentCycle")],
      ["student_status", readControlValue("filterStudentStatus")],
      ["debt_status", readControlValue("filterDebtStatus")],
    ].forEach(([key, value]) => {
      if (!value || value === "all") return;
      params.set(key, value);
    });

    setSearchParams(params);
    loadDirectorDashboard();
  }

  function resetFilters() {
    setSearchParams(new URLSearchParams());
    loadDirectorDashboard();
  }

  function initChart(key, canvasId, configBuilder) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return null;
    if (!dashboardState.charts[key]) {
      dashboardState.charts[key] = new Chart(canvas.getContext("2d"), configBuilder());
    }
    return dashboardState.charts[key];
  }

  async function loadDirectorDashboard() {
    if (!DASHBOARD_API_URL) return;

    try {
      const params = getSearchParams();
      params.set("_", String(Date.now()));
      const response = await fetch(`${DASHBOARD_API_URL}?${params.toString()}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      dashboardState.data = data;
      hydrateFilterOptions(data.filters);
      syncPreserveLinks();
      renderDashboard(data);
    } catch (error) {
      console.error(error);
      renderErrorState();
    }
  }

  function renderErrorState() {
    [
      "todayStrip",
      "trendSignal",
      "problemHub",
      "kpiGrid",
      "financeSignals",
      "groupPreview",
      "teacherBarList",
      "categoryList",
      "studentPreview",
      "insightPreview",
    ].forEach((id) => {
      const element = document.getElementById(id);
      if (element) {
        element.innerHTML = '<div class="empty-state">Panelni yuklashda xatolik yuz berdi.</div>';
      }
    });
  }

  function renderDashboard(data) {
    renderHeader(data);
    renderExecutive(data.executive || {});
    renderKpis(data);
    renderFinance(data);
    renderTeacherPerformance(data.teachers || {});
    renderGroupPreview(data.groups || {});
    renderCategoryBlock(data.finance || {});
    renderStudentPreview(data.students || {});
    renderInsightPreview(data.insights || []);
  }

  function renderHeader(data) {
    const overview = data.overview || {};
    const snapshot = overview.snapshot || {};
    const system = data.system || {};

    const rangeText = snapshot.range_label
      ? `${snapshot.range_label} · ${formatDate(system.start_date)} — ${formatDate(system.end_date)}`
      : `${formatDate(system.start_date)} — ${formatDate(system.end_date)}`;

    const rangeLabel = document.getElementById("heroRangeLabel");
    const lastUpdated = document.getElementById("heroLastUpdated");
    const filterSummary = document.getElementById("filterSummary");

    if (rangeLabel) rangeLabel.textContent = rangeText;
    if (lastUpdated) lastUpdated.textContent = `Oxirgi yangilanish: ${system.last_updated || "--"}`;
    if (filterSummary) {
      filterSummary.textContent = `${snapshot.filter_count || 0} ta faol saralash · ${rangeText}`;
    }
  }

  function renderExecutive(executive) {
    renderTodayStrip(executive.today_strip || []);
    renderTrendSignal(executive.trend_signal || {});
    renderProblemHub(executive.problem_hub || []);
  }

  function renderTodayStrip(items) {
    const container = document.getElementById("todayStrip");
    if (!container) return;
    if (!items.length) {
      container.innerHTML = '<div class="empty-state">Bugungi holat ma\'lumoti topilmadi.</div>';
      return;
    }

    container.innerHTML = items.map((item) => `
      <article class="today-card ${toneClass(item.tone)}">
        <span>${escapeHtml(item.label)}</span>
        <div class="value">${escapeHtml(formatMetricValue(item.value, item.kind))}</div>
        <small>${escapeHtml(item.detail || "")}</small>
      </article>
    `).join("");
  }

  function renderTrendSignal(signal) {
    const container = document.getElementById("trendSignal");
    if (!container) return;
    if (!signal || !signal.title) {
      container.innerHTML = '<div class="empty-state">Trend signali topilmadi.</div>';
      return;
    }

    const chips = Array.isArray(signal.chips) ? signal.chips : [];
    container.innerHTML = `
      <article class="signal-card ${toneClass(signal.tone)}">
        <h3>${escapeHtml(signal.title)}</h3>
        <p>${escapeHtml(signal.text || "")}</p>
        <div class="signal-chip-list">
          ${chips.map((chip) => `
            <span class="metric-pill ${toneClass(signal.tone)}">
              ${escapeHtml(chip.label)}: ${escapeHtml(formatMetricValue(chip.value, chip.kind))}
            </span>
          `).join("")}
        </div>
      </article>
    `;
  }

  function renderProblemHub(items) {
    const container = document.getElementById("problemHub");
    if (!container) return;
    if (!items.length) {
      container.innerHTML = '<div class="empty-state">Muammo markazi uchun ma\'lumot topilmadi.</div>';
      return;
    }

    container.innerHTML = items.map((item) => {
      const detailParts = [];
      if (item.detail_prefix) detailParts.push(item.detail_prefix);
      if (item.detail !== undefined && item.detail !== null && item.detail !== "") {
        detailParts.push(formatMetricValue(item.detail, item.detail_kind || "number"));
      }
      return `
        <article class="problem-item ${toneClass(item.tone)}">
          <span>${escapeHtml(item.label)}</span>
          <div class="value">${escapeHtml(formatMetricValue(item.value, item.kind || "number"))}</div>
          <small>${escapeHtml(detailParts.join(": "))}</small>
        </article>
      `;
    }).join("");
  }

  function renderKpis(data) {
    const finance = data.finance || {};
    const students = data.students || {};
    const overview = data.overview?.kpis || {};
    const items = [
      {
        label: "Daromad",
        icon: "fa-solid fa-wallet",
        accent: "#56d7ff",
        value: fmtMoney(finance.income || 0),
        trend: finance.income_growth,
        sub: "Tanlangan davrdagi jami tushum",
        href: config.links?.payments,
      },
      {
        label: "Sof foyda",
        icon: "fa-solid fa-chart-line",
        accent: "#30d7a1",
        value: fmtMoney(finance.profit || 0),
        trend: finance.profit_growth,
        sub: `Foyda marjasi ${finance.profit_margin || 0}%`,
        href: config.links?.payments,
      },
      {
        label: "Qarzdorlik",
        icon: "fa-solid fa-triangle-exclamation",
        accent: "#ff7188",
        value: fmtMoney(finance.open_debt || 0),
        trend: finance.debt_ratio ? -Number(finance.debt_ratio) : 0,
        sub: `${finance.debtors_count || 0} ta qarzdor o'quvchi`,
        href: config.links?.debtors,
      },
      {
        label: "Aktiv o'quvchilar",
        icon: "fa-solid fa-user-group",
        accent: "#4f7dff",
        value: formatInteger(students.active_students || 0),
        trend: students.growth_pct,
        sub: `Yangi ${students.new_count || 0} · Tark etgan ${students.dropouts || 0}`,
        href: config.links?.students,
      },
      {
        label: "Davomat",
        icon: "fa-solid fa-clipboard-check",
        accent: "#f7c65e",
        value: displayPct(overview.attendance_rate),
        trend: null,
        sub: "Hozirgi filter doirasidagi attendance sifati",
        href: config.links?.lowActivity,
      },
    ];

    const container = document.getElementById("kpiGrid");
    if (!container) return;
    container.innerHTML = items.map((item) => {
      const tag = item.href ? "a" : "article";
      const hrefAttr = item.href ? `href="${escapeHtml(item.href)}" class="kpi-card preserve-link"` : 'class="kpi-card"';
      const baseAttr = item.href ? `data-base-href="${escapeHtml(item.href)}"` : "";
      return `
        <${tag} ${hrefAttr} ${baseAttr} style="--accent:${item.accent}">
          <div class="kpi-top">
            <span class="kpi-icon"><i class="${item.icon}"></i></span>
            <span class="status-chip ${trendClass(item.trend)}">${item.trend === null ? "—" : fmtSignedPct(item.trend)}</span>
          </div>
          <span class="kpi-label">${escapeHtml(item.label)}</span>
          <div class="kpi-value">${escapeHtml(item.value)}</div>
          <div class="kpi-sub">${escapeHtml(item.sub)}</div>
        </${tag}>
      `;
    }).join("");
    syncPreserveLinks();
  }

  function renderFinance(data) {
    const finance = data.finance || {};
    const charts = data.charts || {};

    const financeChart = initChart("financeTrend", "financeTrendChart", () => ({
      type: "line",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        elements: {
          point: { radius: 0, hoverRadius: 4, hitRadius: 16 },
          line: { borderWidth: 2.2 },
        },
        plugins: {
          legend: { display: false },
          tooltip: premiumTooltip({
            label(context) {
              return `${context.dataset.label}: ${fmtMoney(context.parsed.y || 0)}`;
            },
          }),
        },
        scales: {
          x: {
            ticks: { color: "#8da2bc", maxTicksLimit: 8 },
            grid: { display: false },
            border: { display: false },
          },
          y: {
            ticks: {
              color: "#8da2bc",
              callback(value) {
                return fmtCompact(value);
              },
            },
            grid: { color: "rgba(148,163,184,0.08)" },
            border: { display: false },
          },
        },
      },
    }));

    if (financeChart) {
      const incomeGradient = financeChart.ctx.createLinearGradient(0, 0, 0, 260);
      incomeGradient.addColorStop(0, "rgba(86,215,255,0.22)");
      incomeGradient.addColorStop(1, "rgba(86,215,255,0.02)");

      financeChart.data.labels = charts.labels || [];
      financeChart.data.datasets = [
        {
          label: "Daromad",
          data: charts.income || [],
          borderColor: "#56d7ff",
          backgroundColor: incomeGradient,
          tension: 0.34,
          fill: true,
        },
        {
          label: "Xarajat",
          data: charts.expenses || [],
          borderColor: "#ff9d63",
          backgroundColor: "rgba(255,157,99,0.12)",
          pointRadius: 2,
          tension: 0.34,
          fill: false,
        },
        {
          label: "Pul oqimi",
          data: charts.cashflow || [],
          borderColor: "#30d7a1",
          backgroundColor: "rgba(48,215,161,0.1)",
          pointRadius: 2,
          tension: 0.34,
          fill: false,
        },
        {
          label: "Qarzdorlik",
          data: charts.debt_series || [],
          borderColor: "#ff7188",
          backgroundColor: "rgba(255,113,136,0.1)",
          pointRadius: 1,
          tension: 0.24,
          borderDash: [7, 6],
          fill: false,
        },
      ];
      financeChart.update();
    }

    const financeSignals = document.getElementById("financeSignals");
    if (financeSignals) {
      financeSignals.innerHTML = [
        ["Sof pul oqimi", fmtMoney((finance.income || 0) - (finance.expense || 0)), "Daromad va xarajat o'rtasidagi real tafovut"],
        ["Foyda marjasi", `${finance.profit_margin || 0}%`, "Har 100 so'm daromaddan qancha sof foyda qolmoqda"],
        ["Qayta to'lov ulushi", `${finance.recurring_share || 0}%`, "Barqaror tushum sifati va qayta kelayotgan to'lovlar"],
        ["O'rtacha to'lov", fmtCompactMoney(finance.avg_payment || 0), "Bitta to'lov bo'yicha o'rtacha tushum"],
      ].map(([label, value, detail]) => `
        <article class="finance-note">
          <div class="metric-top">
            <strong>${escapeHtml(label)}</strong>
            <span class="value">${escapeHtml(value)}</span>
          </div>
          <small>${escapeHtml(detail)}</small>
        </article>
      `).join("");
    }

    const score = document.getElementById("incomeQualityScore");
    if (score) score.textContent = formatInteger(finance.income_quality_score || 0);

    const agingContainer = document.getElementById("debtAgingBlock");
    if (agingContainer) {
      const aging = finance.debt_aging || {};
      agingContainer.innerHTML = [
        ["0-30 kun", aging["0_30"] || 0],
        ["31-60 kun", aging["31_60"] || 0],
        ["61-90 kun", aging["61_90"] || 0],
        ["90+ kun", aging["90_plus"] || 0],
      ].map(([label, value]) => `
        <article class="metric-item">
          <div class="metric-top">
            <strong>${label}</strong>
            <span class="value">${fmtCompactMoney(value)}</span>
          </div>
        </article>
      `).join("");
    }

    const topDebtors = document.getElementById("topDebtors");
    if (topDebtors) {
      const debtors = finance.top_debtors || [];
      topDebtors.innerHTML = debtors.length
        ? debtors.slice(0, PREVIEW_LIMIT).map((item) => `
            <article class="metric-item">
              <div class="metric-top">
                <strong>${escapeHtml(item.student_name)}</strong>
                <span class="value">${fmtCompactMoney(item.debt || 0)}</span>
              </div>
              <small>${escapeHtml((item.groups || []).join(", ") || "Guruhsiz")}</small>
            </article>
          `).join("")
        : '<div class="empty-state">Qarzdor topilmadi.</div>';
    }
  }

  function renderTeacherPerformance(teachers) {
    const rows = (teachers.ranking || []).slice(0, TEACHER_CHART_LIMIT);
    const chart = initChart("teacherPerformance", "teacherPerformanceChart", () => ({
      type: "bar",
      data: { labels: [], datasets: [{ data: [], backgroundColor: [] }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        plugins: {
          legend: { display: false },
          tooltip: premiumTooltip({
            label(context) {
              const item = rows[context.dataIndex] || {};
              const attendance = item.attendance_rate !== null && item.attendance_rate !== undefined ? `${item.attendance_rate}%` : "Ma'lumot yo'q";
              return `Daromad: ${fmtMoney(context.parsed.x || 0)} · Davomat: ${attendance} · Baho: ${item.health_score || 0}`;
            },
          }),
        },
        datasets: {
          bar: {
            borderRadius: 12,
            barThickness: 18,
          },
        },
        scales: {
          y: {
            ticks: { color: "#8da2bc" },
            grid: { display: false },
            border: { display: false },
          },
          x: {
            ticks: {
              color: "#8da2bc",
              callback(value) {
                return fmtCompact(value);
              },
            },
            grid: { color: "rgba(148,163,184,0.08)" },
            border: { display: false },
          },
        },
      },
    }));

    if (chart) {
      chart.data.labels = rows.map((item) => item.teacher_name);
      chart.data.datasets[0].data = rows.map((item) => Number(item.revenue || 0));
      chart.data.datasets[0].backgroundColor = rows.map((item) => item.health_score >= 75 ? "#30d7a1" : item.health_score >= 55 ? "#56d7ff" : "#f7c65e");
      chart.update();
    }

    const list = document.getElementById("teacherBarList");
    if (!list) return;
    if (!rows.length) {
      list.innerHTML = '<div class="empty-state">Ustozlar bo\'yicha ma\'lumot topilmadi.</div>';
      return;
    }

    const maxRevenue = Math.max(...rows.map((item) => Number(item.revenue || 0)), 1);
    list.innerHTML = rows.slice(0, PREVIEW_LIMIT).map((item) => {
      const width = Math.max(8, Math.round((Number(item.revenue || 0) / maxRevenue) * 100));
      const chipClass = item.health_score >= 75 ? "kuchli" : item.health_score >= 55 ? "barqaror" : "warning";
      return `
        <article class="teacher-rank-item">
          <div class="metric-top">
            <strong>${escapeHtml(item.teacher_name)}</strong>
            <span class="status-chip ${chipClass}">${formatInteger(item.health_score || 0)}</span>
          </div>
          <small>Daromad: ${fmtCompactMoney(item.revenue || 0)} · Sof foyda: ${fmtCompactMoney(item.soft_profit || 0)} · Davomat: ${displayPct(item.attendance_rate)}</small>
          <div class="teacher-progress"><span style="width:${width}%"></span></div>
        </article>
      `;
    }).join("");
  }

  function renderCategoryBlock(finance) {
    const rows = (finance.breakdown?.by_category || []).filter((item) => Number(item.total || 0) > 0);
    const chart = initChart("category", "categoryChart", () => ({
      type: "doughnut",
      data: { labels: [], datasets: [{ data: [], backgroundColor: [] }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "74%",
        plugins: {
          legend: { display: false },
          tooltip: premiumTooltip({
            label(context) {
              return `${context.label}: ${fmtMoney(context.parsed)}`;
            },
          }),
          centerLabel: { label: "Jami", value: "0" },
        },
      },
    }));

    if (chart) {
      const total = rows.reduce((sum, item) => sum + Number(item.total || 0), 0);
      chart.data.labels = rows.map((item) => item["group__category_obj__name"] || "Noma'lum");
      chart.data.datasets[0].data = rows.map((item) => Number(item.total || 0));
      chart.data.datasets[0].backgroundColor = ["#56d7ff", "#4f7dff", "#30d7a1", "#f7c65e", "#ff7188", "#9a84ff"];
      chart.options.plugins.centerLabel.value = fmtCompact(total);
      chart.update();
    }

    const summary = document.getElementById("categorySummary");
    if (summary) {
      if (rows.length) {
        const top = rows[0];
        summary.innerHTML = `
          <div>
            <span class="panel-kicker">Yetakchi kategoriya</span>
            <strong>${escapeHtml(top["group__category_obj__name"] || "Noma'lum")}</strong>
            <small>${rows.length} ta kategoriya orasida eng yuqori tushum</small>
          </div>
          <span class="summary-value">${fmtCompactMoney(top.total || 0)}</span>
        `;
      } else {
        summary.innerHTML = `
          <div>
            <span class="panel-kicker">Kategoriya</span>
            <strong>Ma'lumot topilmadi</strong>
            <small>Tanlangan filtr bo'yicha daromad ko'rinmadi</small>
          </div>
          <span class="summary-value">0</span>
        `;
      }
    }

    const list = document.getElementById("categoryList");
    if (!list) return;
    list.innerHTML = rows.length
      ? rows.slice(0, PREVIEW_LIMIT).map((item) => `
          <article class="metric-item">
            <div class="metric-top">
              <strong>${escapeHtml(item["group__category_obj__name"] || "Noma'lum")}</strong>
              <span class="value">${fmtCompactMoney(item.total || 0)}</span>
            </div>
          </article>
        `).join("")
      : '<div class="empty-state">Ma\'lumot topilmadi.</div>';
  }

  function buildGroupPreviewRows(groups) {
    const unique = new Map();
    [...(groups.top_profitable || []), ...(groups.close_candidates || []), ...(groups.promotion_candidates || [])].forEach((item) => {
      if (item && !unique.has(item.group_id)) {
        unique.set(item.group_id, item);
      }
    });
    return Array.from(unique.values()).slice(0, PREVIEW_LIMIT);
  }

  function renderGroupPreview(groups) {
    const rows = buildGroupPreviewRows(groups);
    const container = document.getElementById("groupPreview");
    if (!container) return;
    if (!rows.length) {
      container.innerHTML = '<div class="empty-state">Guruh tavsiyalari topilmadi.</div>';
      return;
    }

    container.innerHTML = rows.map((item) => `
      <article class="group-card">
        <div class="group-top">
          <div>
            <strong>${escapeHtml(item.group_name)}</strong>
            <p>${escapeHtml(item.teacher_name || "Ustoz biriktirilmagan")} · ${escapeHtml(item.category_name || "Kategoriya yo'q")}</p>
          </div>
          <span class="status-chip ${slugUz(labelHealth(item.health_label))}">${escapeHtml(labelHealth(item.health_label))}</span>
        </div>
        <div class="group-metrics">
          <span class="group-metric">Daromad: ${fmtCompactMoney(item.revenue || 0)}</span>
          <span class="group-metric">Sof foyda: ${fmtCompactMoney(item.soft_profit || 0)}</span>
          <span class="group-metric">Davomat: ${displayPct(item.attendance_rate)}</span>
          <span class="group-metric">Bandlik: ${displayPct(item.fill_rate)}</span>
        </div>
        <p>Tavsiya: ${escapeHtml(item.primary_action || "Kuzatish kerak")}</p>
      </article>
    `).join("");
  }

  function renderStudentPreview(students) {
    const rows = (students.risk_students || []).slice(0, PREVIEW_LIMIT);
    const container = document.getElementById("studentPreview");
    if (!container) return;
    if (!rows.length) {
      container.innerHTML = '<div class="empty-state">Xavfdagi o\'quvchilar topilmadi.</div>';
      return;
    }

    container.innerHTML = rows.map((item) => `
      <article class="student-risk-item">
        <div class="metric-top">
          <strong>${escapeHtml(item.name)}</strong>
          <span class="status-chip ${item.risk_score >= 75 ? "jiddiy" : item.risk_score >= 55 ? "yuqori" : "orta"}">${formatInteger(item.risk_score || 0)}</span>
        </div>
        <p>${escapeHtml(item.course || "Guruhsiz")}</p>
        <div class="risk-metrics">
          <span class="risk-metric">Davomat: ${escapeHtml(item.attendance_pct || "Ma'lumot yo'q")}</span>
          <span class="risk-metric">Qarz: ${fmtCompactMoney(item.debt || 0)}</span>
        </div>
        <p>${escapeHtml(item.reason || "Sabab aniqlanmagan")}</p>
      </article>
    `).join("");
  }

  function resolveInsightTarget(item) {
    const source = `${item.title || ""} ${item.text || ""}`.toLowerCase();
    if (source.includes("lid") || source.includes("manba")) return "marketing";
    if (source.includes("ustoz")) return "teachers";
    if (source.includes("o'quvchi") || source.includes("churn")) return "students";
    if (source.includes("guruh")) return "groups";
    return "insights";
  }

  function renderInsightPreview(insights) {
    const container = document.getElementById("insightPreview");
    if (!container) return;
    if (!insights.length) {
      container.innerHTML = '<div class="empty-state">Aqlli tavsiyalar topilmadi.</div>';
      return;
    }

    container.innerHTML = insights.slice(0, PREVIEW_LIMIT).map((item) => `
      <article class="insight-card">
        <div class="insight-top">
          <div>
            <strong>${escapeHtml(item.title)}</strong>
            <p>${escapeHtml(item.text || "")}</p>
          </div>
          <span class="status-chip ${slugUz(labelSeverity(item.severity))}">${escapeHtml(labelSeverity(item.severity))}</span>
        </div>
        <button type="button" class="insight-action" data-open-drawer="${escapeHtml(resolveInsightTarget(item))}">
          ${escapeHtml(labelAction(item.action_type))}
        </button>
      </article>
    `).join("");
  }

  function getDrawerConfig(type) {
    const data = dashboardState.data || {};
    return {
      groups: {
        kicker: "Guruhlar",
        title: "Guruhlar rentabelligi",
        subtitle: "Guruhlarning to'liq ro'yxati, holat bahosi va tavsiya etilgan harakatlar",
        items: data.groups?.profitability || [],
        searchText: (item) => `${item.group_name} ${item.teacher_name} ${item.category_name} ${item.primary_action}`,
        render: (item) => `
          <article class="drawer-item">
            <div class="drawer-top">
              <h4>${escapeHtml(item.group_name)}</h4>
              <span class="status-chip ${slugUz(labelHealth(item.health_label))}">${escapeHtml(labelHealth(item.health_label))} · ${formatInteger(item.health_score || 0)}</span>
            </div>
            <p>Ustoz: ${escapeHtml(item.teacher_name || "Biriktirilmagan")} · Kategoriya: ${escapeHtml(item.category_name || "Noma'lum")}</p>
            <p>Daromad: ${fmtMoney(item.revenue || 0)} · Sof foyda: ${fmtMoney(item.soft_profit || 0)} · Qarz: ${fmtMoney(item.open_debt || 0)}</p>
            <p>Davomat: ${displayPct(item.attendance_rate)} · Bandlik: ${displayPct(item.fill_rate)} · Tark etish xavfi: ${displayPct(item.churn_risk)}</p>
            <div class="drawer-meta">
              <span class="status-chip ${slugUz(labelAction(item.action_type))}">${escapeHtml(item.primary_action || "-")}</span>
            </div>
          </article>
        `,
      },
      teachers: {
        kicker: "Ustozlar",
        title: "Ustozlar samaradorligi",
        subtitle: "Daromad, foyda, davomat va saqlab qolish bo'yicha to'liq ko'rinish",
        items: data.teachers?.ranking || [],
        searchText: (item) => `${item.teacher_name} ${item.revenue} ${item.health_score}`,
        render: (item) => `
          <article class="drawer-item">
            <div class="drawer-top">
              <h4>${escapeHtml(item.teacher_name)}</h4>
              <span class="status-chip ${item.health_score >= 75 ? "kuchli" : item.health_score >= 55 ? "barqaror" : "warning"}">${formatInteger(item.health_score || 0)}</span>
            </div>
            <p>Daromad: ${fmtMoney(item.revenue || 0)} · Sof foyda: ${fmtMoney(item.soft_profit || 0)}</p>
            <p>Guruhlar: ${formatInteger(item.groups || 0)} · O'quvchilar: ${formatInteger(item.students || 0)} · Davomat: ${displayPct(item.attendance_rate)}</p>
            <p>Saqlab qolish: ${displayPct(item.retention_rate)} · Qarz ulushi: ${displayPct(item.debt_ratio)}</p>
          </article>
        `,
      },
      students: {
        kicker: "O'quvchilar",
        title: "Xavfdagi o'quvchilar",
        subtitle: "Chiqib ketish xavfi yuqori yoki kam faol o'quvchilar ro'yxati",
        items: data.students?.risk_students || [],
        searchText: (item) => `${item.name} ${item.course} ${item.reason}`,
        render: (item) => `
          <article class="drawer-item">
            <div class="drawer-top">
              <h4>${escapeHtml(item.name)}</h4>
              <span class="status-chip ${item.risk_score >= 75 ? "jiddiy" : item.risk_score >= 55 ? "yuqori" : "orta"}">${formatInteger(item.risk_score || 0)}</span>
            </div>
            <p>Guruh: ${escapeHtml(item.course || "Guruhsiz")} · Davomat: ${escapeHtml(item.attendance_pct || "Ma'lumot yo'q")}</p>
            <p>Qarz: ${fmtMoney(item.debt || 0)} · Sabab: ${escapeHtml(item.reason || "-")}</p>
          </article>
        `,
      },
      marketing: {
        kicker: "Marketing",
        title: "Lid manbalari tahlili",
        subtitle: "Har bir manbaning konversiyasi, tushumi va samaradorlik bahosi",
        items: data.marketing?.sources || [],
        searchText: (item) => `${item.name} ${item.count} ${item.conversion}`,
        render: (item) => `
          <article class="drawer-item">
            <div class="drawer-top">
              <h4>${escapeHtml(item.name)}</h4>
              <span class="status-chip ${item.source_efficiency_score >= 70 ? "kuchli" : item.source_efficiency_score >= 50 ? "barqaror" : "warning"}">${formatInteger(item.source_efficiency_score || 0)}</span>
            </div>
            <p>Lidlar: ${formatInteger(item.count || 0)} ta · Konversiya: ${displayPct(item.conversion)} · Faol o'quvchi: ${formatInteger(item.active_students || 0)}</p>
            <p>Daromad: ${fmtMoney(item.revenue || 0)} · Sinov dars: ${formatInteger(item.trial_scheduled || 0)} · Qatnashgan: ${formatInteger(item.trial_attended || 0)}</p>
          </article>
        `,
      },
      insights: {
        kicker: "Aqlli tavsiyalar",
        title: "Barcha insightlar",
        subtitle: "Filtr doirasida aniqlangan barcha avtomatik tavsiyalar",
        items: data.insights || [],
        searchText: (item) => `${item.title} ${item.text} ${item.severity} ${item.action_type}`,
        render: (item) => `
          <article class="drawer-item">
            <div class="drawer-top">
              <h4>${escapeHtml(item.title)}</h4>
              <div class="drawer-meta">
                <span class="status-chip ${slugUz(labelSeverity(item.severity))}">${escapeHtml(labelSeverity(item.severity))}</span>
                <span class="status-chip ${slugUz(labelAction(item.action_type))}">${escapeHtml(labelAction(item.action_type))}</span>
              </div>
            </div>
            <p>${escapeHtml(item.text || "")}</p>
          </article>
        `,
      },
    }[type];
  }

  function getDrawerDataset() {
    const configForType = getDrawerConfig(dashboardState.drawer.type);
    if (!configForType) {
      return { config: null, filtered: [], pageItems: [], totalPages: 1, page: 1 };
    }
    const query = (dashboardState.drawer.query || "").trim().toLowerCase();
    const filtered = (configForType.items || []).filter((item) => {
      if (!query) return true;
      return String(configForType.searchText(item) || "").toLowerCase().includes(query);
    });
    const totalPages = Math.max(1, Math.ceil(filtered.length / DRAWER_PAGE_SIZE));
    const page = Math.min(dashboardState.drawer.page, totalPages);
    const startIndex = (page - 1) * DRAWER_PAGE_SIZE;
    const pageItems = filtered.slice(startIndex, startIndex + DRAWER_PAGE_SIZE);
    return { config: configForType, filtered, pageItems, totalPages, page };
  }

  function openDrawer(type) {
    dashboardState.drawer.type = type;
    dashboardState.drawer.page = 1;
    dashboardState.drawer.query = "";
    const searchInput = document.getElementById("drawerSearch");
    if (searchInput) searchInput.value = "";
    document.getElementById("drawerBackdrop")?.classList.add("open");
    document.getElementById("detailDrawer")?.classList.add("open");
    document.getElementById("detailDrawer")?.setAttribute("aria-hidden", "false");
    renderDrawer();
  }

  function closeDrawer() {
    document.getElementById("drawerBackdrop")?.classList.remove("open");
    document.getElementById("detailDrawer")?.classList.remove("open");
    document.getElementById("detailDrawer")?.setAttribute("aria-hidden", "true");
  }

  function renderDrawer() {
    const drawerData = getDrawerDataset();
    if (!drawerData.config) return;

    const { config: drawerConfig, filtered, pageItems, totalPages, page } = drawerData;
    const kicker = document.getElementById("drawerKicker");
    const title = document.getElementById("drawerTitle");
    const subtitle = document.getElementById("drawerSubtitle");
    const counter = document.getElementById("drawerCounter");
    const pageLabel = document.getElementById("drawerPage");
    const prev = document.getElementById("drawerPrev");
    const next = document.getElementById("drawerNext");
    const body = document.getElementById("drawerBody");

    if (kicker) kicker.textContent = drawerConfig.kicker;
    if (title) title.textContent = drawerConfig.title;
    if (subtitle) subtitle.textContent = drawerConfig.subtitle;
    if (counter) counter.textContent = `${filtered.length} ta natija`;
    if (pageLabel) pageLabel.textContent = `${page} / ${totalPages}`;
    if (prev) prev.disabled = page <= 1;
    if (next) next.disabled = page >= totalPages;
    if (body) {
      body.innerHTML = pageItems.length
        ? pageItems.map((item) => drawerConfig.render(item)).join("")
        : '<div class="empty-state">Ma\'lumot topilmadi.</div>';
    }
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDrawer();
  });

  document.addEventListener("DOMContentLoaded", () => {
    bindToolbar();
    bindInteractionDelegation();
    bindDrawer();
    syncPreserveLinks();
    loadDirectorDashboard();
  });
})();
