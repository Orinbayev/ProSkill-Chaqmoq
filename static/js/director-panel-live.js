(function () {
  const config = window.directorPanelConfig || {};
  const API_URL = config.apiUrl || "";
  const AI_INSIGHTS_URL = config.aiInsightsUrl || "";
  const AI_CHURN_URL = config.aiChurnRiskUrl || "";
  const AI_FORECAST_URL = config.aiForecastUrl || "";
  const AI_ASK_URL = config.aiAskUrl || "";
  const AI_CHAT_URL = config.aiChatUrl || "";
  const AI_CHAT_RESET_URL = config.aiChatResetUrl || "";
  const AI_CHAT_ASK_URL = config.aiChatAskUrl || AI_ASK_URL;
  const AI_CHAT_POSITION_URL = config.aiChatPositionUrl || "";
  const CURRENT_USER_NAME = config.currentUserName || "Siz";
  const CURRENT_USER_INITIAL = (config.currentUserInitial || CURRENT_USER_NAME || "S").slice(0, 1).toUpperCase();
  const COLORS = {
    amber: "#f59e0b",
    amberSoft: "rgba(245,158,11,0.18)",
    cyan: "#3b82f6",
    cyanSoft: "rgba(59,130,246,0.18)",
    emerald: "#22c55e",
    emeraldSoft: "rgba(34,197,94,0.18)",
    rose: "#ef4444",
    roseSoft: "rgba(239,68,68,0.18)",
    violet: "#6366f1",
    slate: "#94a3b8",
    white: "#f8fafc",
  };
  const MONTH_NAMES = [
    "yanvar",
    "fevral",
    "mart",
    "aprel",
    "may",
    "iyun",
    "iyul",
    "avgust",
    "sentyabr",
    "oktyabr",
    "noyabr",
    "dekabr",
  ];
  const MONTH_TOKEN_MAP = {
    jan: 1,
    january: 1,
    feb: 2,
    february: 2,
    mar: 3,
    march: 3,
    apr: 4,
    april: 4,
    may: 5,
    jun: 6,
    june: 6,
    jul: 7,
    july: 7,
    aug: 8,
    august: 8,
    sep: 9,
    sept: 9,
    september: 9,
    oct: 10,
    october: 10,
    nov: 11,
    november: 11,
    dec: 12,
    december: 12,
  };

  const state = {
    period: "bu_oy",
    activeTab: "manager",
    data: null,
    charts: {},
    sparkCharts: {},
    modalChart: null,
    modalDetailTarget: null,
    hydrating: false,
    kpiSeries: {},
    aiRefreshTimer: null,
    seriesVisible: {
      income: true,
      expenses: true,
      cashflow: true,
      debt: true,
    },
    ai: {
      insights: [],
      churn: { items: [], summary: {} },
      forecast: { items: [], summary: {} },
      requestToken: 0,
    },
    chat: {
      initialized: false,
      loading: false,
      open: false,
      messages: [],
      session: null,
      position: { x: null, y: null },
      dragging: false,
      dragOffsetX: 0,
      dragOffsetY: 0,
      activeDragTarget: null,
      dragMoved: false,
      suppressToggleUntil: 0,
    },
  };

  function el(id) {
    return document.getElementById(id);
  }

  function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatInteger(value) {
    return new Intl.NumberFormat("uz-UZ").format(Math.round(Number(value || 0)));
  }

  function compactNumber(value) {
    const num = Number(value || 0);
    const abs = Math.abs(num);
    const prefix = num < 0 ? "-" : "";
    if (abs >= 1e9) return `${prefix}${(abs / 1e9).toFixed(1)} mlrd`;
    if (abs >= 1e6) return `${prefix}${(abs / 1e6).toFixed(1)} mln`;
    if (abs >= 1e3) return `${prefix}${Math.round(abs / 1e3)} ming`;
    return `${prefix}${Math.round(abs)}`;
  }

  function compactMoney(value) {
    return `${compactNumber(value)} UZS`;
  }

  function signedPct(value) {
    if (value === null || value === undefined || value === "") return "0%";
    const num = Number(value || 0);
    return `${num > 0 ? "+" : ""}${num.toFixed(1)}%`;
  }

  function displayPct(value) {
    if (value === null || value === undefined || value === "") return "0%";
    return `${Number(value || 0).toFixed(1)}%`;
  }

  function percentOf(part, total) {
    if (!total) return 0;
    return Math.max(0, Math.min(100, (Number(part || 0) / Number(total || 0)) * 100));
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function toneClassByValue(value) {
    const num = Number(value || 0);
    if (num > 0) return "cg";
    if (num < 0) return "cr";
    return "cn";
  }

  function healthChip(metric) {
    const score = Number(metric?.health_score || 0);
    if (score >= 75) return "cg";
    if (score >= 55) return "cc";
    if (score >= 40) return "cy";
    return "cr";
  }

  function statusChipClass(label) {
    const value = String(label || "").toLowerCase();
    if (value.includes("tasdiq")) return "cg";
    if (value.includes("rad")) return "cr";
    if (value.includes("risk")) return "cr";
    if (value.includes("faol")) return "cg";
    if (value.includes("noaktiv")) return "cy";
    if (value.includes("guruhsiz")) return "cc";
    if (value.includes("kutil")) return "cy";
    return "cn";
  }

  function initials(name) {
    return String(name || "")
      .split(/\s+/)
      .filter(Boolean)
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();
  }

  function currentPreset() {
    if (state.period === "custom") return "custom";
    return state.period === "otgan_oy" ? "last_month" : "this_month";
  }

  function nowText() {
    const now = new Date();
    return `${now.toLocaleDateString("uz-UZ", { day: "2-digit", month: "2-digit", year: "numeric" })} - ${now.toLocaleTimeString("uz-UZ")}`;
  }

  function formatChatTime(value) {
    if (!value) return nowText();
    const dateValue = new Date(value);
    if (Number.isNaN(dateValue.getTime())) return String(value);
    return dateValue.toLocaleString("uz-UZ", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function monthName(monthNumber) {
    return MONTH_NAMES[Number(monthNumber || 0) - 1] || "";
  }

  function parseDateLabel(value) {
    if (!value && value !== 0) return null;
    const raw = String(value).trim();
    if (!raw) return null;

    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      const [year, month, day] = raw.split("-").map(Number);
      return { year, month, day };
    }

    if (/^\d{2}\.\d{2}\.\d{4}$/.test(raw)) {
      const [day, month, year] = raw.split(".").map(Number);
      return { year, month, day };
    }

    if (/^\d{2}\.\d{2}$/.test(raw)) {
      const [day, month] = raw.split(".").map(Number);
      const systemStart = String(state.data?.system?.start_date || "");
      const systemEnd = String(state.data?.system?.end_date || "");
      let inferredYear = new Date().getFullYear();
      if (/^\d{4}-\d{2}-\d{2}$/.test(systemStart) && /^\d{4}-\d{2}-\d{2}$/.test(systemEnd)) {
        const startYear = Number(systemStart.slice(0, 4));
        const startMonth = Number(systemStart.slice(5, 7));
        const endYear = Number(systemEnd.slice(0, 4));
        const endMonth = Number(systemEnd.slice(5, 7));
        if (startYear !== endYear) {
          inferredYear = month >= startMonth ? startYear : endYear;
        } else {
          inferredYear = endYear;
        }
        if (startMonth === month) inferredYear = startYear;
        if (endMonth === month) inferredYear = endYear;
      } else if (/^\d{4}-\d{2}-\d{2}$/.test(systemEnd)) {
        inferredYear = Number(systemEnd.slice(0, 4));
      }
      return { year: inferredYear, month, day };
    }

    const normalized = raw.replace(",", " ").replace(/\s+/g, " ").trim();
    const parts = normalized.split(" ");
    if (parts.length >= 2) {
      const month = MONTH_TOKEN_MAP[parts[0].toLowerCase()];
      const year = Number(parts[1]);
      if (month && Number.isFinite(year)) {
        return { year, month, day: 1 };
      }
    }

    return null;
  }

  function formatApiDate(value, options = {}) {
    if (!value && value !== 0) return "";
    const parsed = parseDateLabel(value);
    if (!parsed) return String(value);

    const includeYear = options.includeYear !== false;
    const multiline = !!options.multiline;
    const dayPart = parsed.day ? String(parsed.day) : "";
    const monthPart = monthName(parsed.month);

    if (multiline) {
      if (dayPart && monthPart) return [dayPart, monthPart];
      if (monthPart && includeYear) return [monthPart, `${parsed.year}`];
      return dayPart || monthPart || String(value);
    }

    if (dayPart && monthPart) {
      return includeYear ? `${parsed.year}-yil ${dayPart}-${monthPart}` : `${dayPart}-${monthPart}`;
    }
    if (monthPart) {
      return includeYear ? `${monthPart} ${parsed.year}` : monthPart;
    }
    return String(value);
  }

  function formatDateRange(start, end) {
    const startText = formatApiDate(start, { includeYear: true });
    const endText = formatApiDate(end, { includeYear: true });
    if (!startText && !endText) return "Tanlangan davr";
    if (!startText) return endText;
    if (!endText) return startText;
    return `${startText} dan ${endText} gacha`;
  }

  function tickClock() {
    const clock = el("hdr-clock");
    if (clock) clock.textContent = nowText();
    setTimeout(tickClock, 1000);
  }

  function updateMeta(rangeText) {
    const meta = el("dashboardMeta");
    if (!meta) return;
    meta.innerHTML = `${escapeHtml(rangeText || "ChaqmoqApp CRM")} - <span id="hdr-clock">${escapeHtml(nowText())}</span>`;
  }

  function setPeriodUi() {
    const activeBg = "linear-gradient(135deg, rgba(245,158,11,.2), rgba(59,130,246,.12))";
    const activeColor = COLORS.amber;
    const inactiveBg = "transparent";
    const inactiveColor = "rgba(255,255,255,.38)";
    const bu = el("btn-bu");
    const otgan = el("btn-otgan");
    if (bu) {
      bu.style.background = state.period === "bu_oy" ? activeBg : inactiveBg;
      bu.style.color = state.period === "bu_oy" ? activeColor : inactiveColor;
    }
    if (otgan) {
      otgan.style.background = state.period === "otgan_oy" ? activeBg : inactiveBg;
      otgan.style.color = state.period === "otgan_oy" ? activeColor : inactiveColor;
    }
  }

  function setPeriod(period) {
    state.period = period === "otgan_oy" ? "otgan_oy" : "bu_oy";
    const fromInput = el("dateFromInput");
    const toInput = el("dateToInput");
    if (fromInput) fromInput.value = "";
    if (toInput) toInput.value = "";
    setPeriodUi();
    loadDashboard();
  }

  function fillSelect(selectId, items, prefix, selected) {
    const select = el(selectId);
    if (!select) return;
    select.innerHTML = "";

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = `${prefix}: Barchasi`;
    select.appendChild(defaultOption);

    (items || []).forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = `${prefix}: ${item.name}`;
      select.appendChild(option);
    });

    select.value = selected || "";
  }

  function hydrateFilters(filters) {
    if (!filters) return;
    state.hydrating = true;
    const options = filters.options || {};
    const applied = filters.applied || {};
    if (applied.preset === "last_month") state.period = "otgan_oy";
    else if (applied.preset === "custom") state.period = "custom";
    else state.period = "bu_oy";
    fillSelect("branchSelect", options.branches || [], "Filial", (applied.branch_ids || [])[0] || "");
    fillSelect("teacherSelect", options.teachers || [], "Ustoz", (applied.teacher_ids || [])[0] || "");
    fillSelect("categorySelect", options.categories || [], "Bo'lim", (applied.category_ids || [])[0] || "");
    if (el("dateFromInput")) el("dateFromInput").value = applied.date_from || "";
    if (el("dateToInput")) el("dateToInput").value = applied.date_to || "";
    state.hydrating = false;
    setPeriodUi();
  }

  function buildQuery() {
    const params = new URLSearchParams();
    const branch = el("branchSelect")?.value;
    const teacher = el("teacherSelect")?.value;
    const category = el("categorySelect")?.value;
    const dateFrom = String(el("dateFromInput")?.value || "").trim();
    const dateTo = String(el("dateToInput")?.value || "").trim();

    if (dateFrom && dateTo && dateFrom <= dateTo) {
      params.set("preset", "custom");
      params.set("date_from", dateFrom);
      params.set("date_to", dateTo);
    } else {
      params.set("preset", currentPreset());
    }

    if (branch) params.set("branch", branch);
    if (teacher) params.set("teacher", teacher);
    if (category) params.set("category", category);
    params.set("_", String(Date.now()));
    return params;
  }

  function buildUrl(baseUrl) {
    const query = buildQuery().toString();
    return query ? `${baseUrl}?${query}` : baseUrl;
  }

  async function fetchJson(baseUrl, options = {}) {
    const response = await fetch(buildUrl(baseUrl), {
      credentials: "same-origin",
      ...options,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  function setChipState(id, text, tone = "cn") {
    const node = el(id);
    if (!node) return;
    node.className = `chip ${tone}`;
    node.textContent = text;
  }

  function setLoading(isLoading) {
    const button = el("refreshDashboardBtn");
    if (!button) return;
    button.style.opacity = isLoading ? ".55" : "1";
    button.style.pointerEvents = isLoading ? "none" : "auto";
  }

  async function loadDashboard() {
    if (!API_URL) return;
    setLoading(true);
    if (state.aiRefreshTimer) window.clearTimeout(state.aiRefreshTimer);
    renderAiLoading();
    try {
      const payload = await fetchJson(API_URL);
      state.data = payload;
      hydrateFilters(payload.filters);
      renderAll();
      loadAiWidgets();
    } catch (error) {
      console.error(error);
      renderErrorState();
    } finally {
      setLoading(false);
    }
  }

  function renderErrorState() {
    [
      "directory-summary-grid",
      "directory-note",
      "lead-pulse-meta",
      "ai-insights-list",
      "churn-risk-list",
    ].forEach((id) => {
      const node = el(id);
      if (node) node.innerHTML = '<div class="loading-shell">Dashboardni yuklashda xatolik yuz berdi.</div>';
    });

    [
      "kpi-grid",
      "directory-table",
      "teacher-tbl",
      "groups-tbl",
      "goals-wrap",
      "pay-legend",
      "rev-legend",
    ].forEach((id) => {
      const node = el(id);
      if (node) node.innerHTML = '<div class="loading-shell">Xatolik yuz berdi.</div>';
    });
    setChipState("aiInsightsMeta", "Xatolik", "cr");
    setChipState("churnSummaryChip", "Xatolik", "cr");
    setChipState("forecastMetaChip", "Xatolik", "cr");
  }

  function metricTile(label, value, sub, accentClass) {
    return `
      <div class="summary-tile">
        <span class="label">${escapeHtml(label)}</span>
        <div class="value ${accentClass || ""}">${escapeHtml(value)}</div>
        <div class="sub">${escapeHtml(sub || "")}</div>
      </div>
    `;
  }

  function stackRow(title, sub, tail, tailColor) {
    return `
      <div class="stack-item">
        <div>
          <strong>${escapeHtml(title)}</strong>
          <small>${escapeHtml(sub || "")}</small>
        </div>
        <div class="tail" style="${tailColor ? `color:${tailColor};` : ""}">${escapeHtml(tail)}</div>
      </div>
    `;
  }

  function setDirectoryShell(config) {
    if (el("directory-kicker")) el("directory-kicker").textContent = config.kicker || "";
    if (el("directory-title")) el("directory-title").textContent = config.title || "";
    if (el("directory-count")) {
      el("directory-count").className = `chip ${config.countTone || "cy"}`;
      el("directory-count").textContent = config.countText || "";
    }
    if (el("directory-note")) el("directory-note").textContent = config.note || "";
  }

  function renderManagerDirectory() {
    const managers = state.data?.managers || {};
    const ranking = managers.ranking || [];
    const top = ranking[0];
    const approvedTotal = ranking.reduce((sum, row) => sum + Number(row.approved_requests || 0), 0);
    const salesTotal = ranking.reduce((sum, row) => sum + Number(row.sales_count || 0), 0);

    setDirectoryShell({
      kicker: "MANAGERLAR",
      title: "Barcha managerlar ro'yxati",
      countText: `${formatInteger(managers.total_count || ranking.length)} manager`,
      countTone: "cy",
      note: top
        ? `${top.manager_name} hozir yetakchi: ${formatInteger(top.leads)} lead, ${formatInteger(top.converted)} aylangan lead va ${displayPct(top.conversion_rate)} konversiya.`
        : "Tanlangan filtr bo'yicha manager ma'lumoti topilmadi.",
    });

    if (el("directory-summary-grid")) {
      el("directory-summary-grid").innerHTML = [
        metricTile("Jami manager", formatInteger(managers.total_count || ranking.length), "Markaz bo'yicha faol nazoratchilar"),
        metricTile("Jami lead", formatInteger(managers.total_leads || 0), "Managerlarga biriktirilgan lidlar"),
        metricTile("Aylangan lead", formatInteger(managers.total_converted || 0), "Talabaga o'tganlar"),
        metricTile("So'rov / savdo", `${formatInteger(approvedTotal)} / ${formatInteger(salesTotal)}`, "Do'kon so'rovi va sotuvlari"),
      ].join("");
    }

    const table = el("directory-table");
    if (!table) return;
    if (!ranking.length) {
      table.innerHTML = '<tbody><tr><td>Manager ma\'lumoti topilmadi.</td></tr></tbody>';
      return;
    }
    table.innerHTML = `
      <thead>
        <tr>
          <th>#</th>
          <th style="text-align:left;">Manager</th>
          <th style="text-align:center;">Lead</th>
          <th style="text-align:center;">Aylangan</th>
          <th style="text-align:center;">Takip</th>
          <th style="text-align:center;">So'rov</th>
          <th style="text-align:center;">Savdo</th>
          <th style="text-align:right;">Konversiya</th>
        </tr>
      </thead>
      <tbody>
        ${ranking.map((row, index) => `
          <tr>
            <td>${index + 1}</td>
            <td>
              <div style="display:flex;align-items:center;gap:8px;">
                <div style="width:28px;height:28px;border-radius:50%;background:${index % 2 === 0 ? COLORS.amber : COLORS.cyan};color:#071018;display:flex;align-items:center;justify-content:center;font-size:.59rem;font-weight:800;flex-shrink:0;">${escapeHtml(initials(row.manager_name))}</div>
                <div>
                  <div style="font-weight:700;color:${COLORS.white};">${escapeHtml(row.manager_name)}</div>
                  <div style="font-size:.65rem;color:rgba(255,255,255,.35);">${escapeHtml(row.focus_note || "")}</div>
                </div>
              </div>
            </td>
            <td style="text-align:center;color:${COLORS.cyan};font-weight:700;">${formatInteger(row.leads)}</td>
            <td style="text-align:center;color:${COLORS.emerald};font-weight:700;">${formatInteger(row.converted)}</td>
            <td style="text-align:center;color:${COLORS.amber};font-weight:700;">${formatInteger(row.pending_followups)}</td>
            <td style="text-align:center;color:${COLORS.violet};font-weight:700;">${formatInteger(row.approved_requests)}</td>
            <td style="text-align:center;color:${COLORS.rose};font-weight:700;">${formatInteger(row.sales_count || 0)}</td>
            <td style="text-align:right;font-weight:800;color:${COLORS.white};">${displayPct(row.conversion_rate)}</td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderTeacherDirectory() {
    const teachers = state.data?.teachers || {};
    const ranking = teachers.ranking || [];
    const top = ranking[0];
    const avgHealth = ranking.length ? ranking.reduce((sum, row) => sum + Number(row.health_score || 0), 0) / ranking.length : 0;
    const totalGroups = ranking.reduce((sum, row) => sum + Number(row.groups || 0), 0);
    const totalStudents = ranking.reduce((sum, row) => sum + Number(row.students || 0), 0);

    setDirectoryShell({
      kicker: "O'QITUVCHILAR",
      title: "Barcha o'qituvchilar ro'yxati",
      countText: `${formatInteger(teachers.total_count || ranking.length)} ustoz`,
      countTone: "cc",
      note: top
        ? `${top.teacher_name} eng kuchli ustoz: ${compactMoney(top.revenue || 0)} daromad, ${formatInteger(top.students || 0)} o'quvchi va ${formatInteger(top.health_score || 0)} health score.`
        : "Tanlangan filtr bo'yicha ustoz ma'lumoti topilmadi.",
    });

    if (el("directory-summary-grid")) {
      el("directory-summary-grid").innerHTML = [
        metricTile("Jami ustoz", formatInteger(teachers.total_count || ranking.length), "Aktiv o'qituvchilar"),
        metricTile("Jami guruh", formatInteger(totalGroups), "Biriktirilgan guruhlar"),
        metricTile("Jami o'quvchi", formatInteger(totalStudents), "Ustozlar kesimida"),
        metricTile("O'rtacha baho", formatInteger(avgHealth), "Health score bo'yicha"),
      ].join("");
    }

    renderTeacherTable("directory-table", ranking, true);
  }

  function renderStudentDirectory() {
    const students = state.data?.students || {};
    const roster = students.roster || [];
    const riskCount = roster.filter((row) => row.status_label === "Riskda").length;

    setDirectoryShell({
      kicker: "O'QUVCHILAR",
      title: "Barcha o'quvchilar ro'yxati",
      countText: `${formatInteger(students.total || roster.length)} o'quvchi`,
      countTone: "cg",
      note: `${formatInteger(students.new_count || 0)} yangi o'quvchi qo'shilgan, ${formatInteger(riskCount)} tasi riskda, ${formatInteger(students.debtors_count || 0)} tasi qarzdor holatda.`,
    });

    if (el("directory-summary-grid")) {
      el("directory-summary-grid").innerHTML = [
        metricTile("Jami o'quvchi", formatInteger(students.total || roster.length), "Tanlangan filtr doirasida"),
        metricTile("Faol o'quvchi", formatInteger(students.active_students || 0), `${signedPct(students.growth_pct || 0)} o'sish`),
        metricTile("Riskdagi", formatInteger(riskCount), "Aralashuv talab qilinadi"),
        metricTile("Qarzdor", formatInteger(students.debtors_count || 0), compactMoney(students.debt_amount || 0)),
      ].join("");
    }

    const table = el("directory-table");
    if (!table) return;
    if (!roster.length) {
      table.innerHTML = '<tbody><tr><td>O\'quvchilar ro\'yxati topilmadi.</td></tr></tbody>';
      return;
    }
    table.innerHTML = `
      <thead>
        <tr>
          <th style="text-align:left;">O'quvchi</th>
          <th style="text-align:left;">Guruh</th>
          <th style="text-align:center;">Holat</th>
          <th style="text-align:center;">Davomat</th>
          <th style="text-align:right;">Qarz</th>
          <th style="text-align:center;">Risk</th>
          <th style="text-align:right;">Qo'shilgan</th>
        </tr>
      </thead>
      <tbody>
        ${roster.map((row) => `
          <tr>
            <td><span style="font-weight:700;color:${COLORS.white};">${escapeHtml(row.name)}</span></td>
            <td><span style="color:rgba(255,255,255,.48);">${escapeHtml(row.course || "Guruhsiz")}</span></td>
            <td style="text-align:center;"><span class="chip ${statusChipClass(row.status_label)}">${escapeHtml(row.status_label || "-")}</span></td>
            <td style="text-align:center;color:${COLORS.cyan};font-weight:700;">${escapeHtml(row.attendance_pct || "Ma'lumot yo'q")}</td>
            <td style="text-align:right;color:${COLORS.amber};font-weight:700;">${compactMoney(row.debt || 0)}</td>
            <td style="text-align:center;"><span class="chip ${Number(row.risk_score || 0) >= 70 ? "cr" : Number(row.risk_score || 0) >= 45 ? "cy" : "cg"}">${formatInteger(row.risk_score || 0)}</span></td>
            <td style="text-align:right;color:rgba(255,255,255,.42);">${escapeHtml(row.joined_at || "-")}</td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderRequestDirectory() {
    const requests = state.data?.requests || {};
    const items = requests.items || [];
    const topProduct = (requests.top_products || [])[0];

    setDirectoryShell({
      kicker: "SO'ROVLAR",
      title: "Yuborilgan so'rovlar ro'yxati",
      countText: `${formatInteger(requests.total_count || items.length)} so'rov`,
      countTone: "cp",
      note: topProduct
        ? `${topProduct.name} eng ko'p so'ralgan mahsulot: ${formatInteger(topProduct.count)} ta so'rov va ${formatInteger(topProduct.qty)} dona.`
        : "Tanlangan filtr bo'yicha yuborilgan so'rov topilmadi.",
    });

    if (el("directory-summary-grid")) {
      el("directory-summary-grid").innerHTML = [
        metricTile("Jami so'rov", formatInteger(requests.total_count || items.length), `${signedPct(requests.growth || 0)} o'zgarish`),
        metricTile("Kutilmoqda", formatInteger(requests.pending_count || 0), "Ko'rib chiqilishi kerak"),
        metricTile("Tasdiqlandi", formatInteger(requests.approved_count || 0), "Qabul qilinganlar"),
        metricTile("Qiymat", compactMoney(requests.total_value_som || 0), `${formatInteger(requests.total_value_chaqmoq || 0)} chaqmoq`),
      ].join("");
    }

    const table = el("directory-table");
    if (!table) return;
    if (!items.length) {
      table.innerHTML = '<tbody><tr><td>Yuborilgan so\'rovlar topilmadi.</td></tr></tbody>';
      return;
    }
    table.innerHTML = `
      <thead>
        <tr>
          <th style="text-align:left;">O'quvchi</th>
          <th style="text-align:left;">Mahsulot</th>
          <th style="text-align:center;">Soni</th>
          <th style="text-align:center;">Holat</th>
          <th style="text-align:left;">Manager</th>
          <th style="text-align:right;">Qiymat</th>
          <th style="text-align:right;">Sana</th>
        </tr>
      </thead>
      <tbody>
        ${items.map((row) => `
          <tr>
            <td><span style="font-weight:700;color:${COLORS.white};">${escapeHtml(row.student_name)}</span></td>
            <td><span style="color:rgba(255,255,255,.58);">${escapeHtml(row.product_name)}</span></td>
            <td style="text-align:center;color:${COLORS.cyan};font-weight:700;">${formatInteger(row.qty || 0)}</td>
            <td style="text-align:center;"><span class="chip ${statusChipClass(row.status_label)}">${escapeHtml(row.status_label)}</span></td>
            <td style="color:rgba(255,255,255,.58);">${escapeHtml(row.manager_name || "Biriktirilmagan")}</td>
            <td style="text-align:right;color:${COLORS.amber};font-weight:700;">${compactMoney(row.value_som || 0)}</td>
            <td style="text-align:right;color:rgba(255,255,255,.42);">${escapeHtml(row.created_at)}</td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderDirectoryPanel() {
    if (state.activeTab === "teachers") {
      renderTeacherDirectory();
      return;
    }
    if (state.activeTab === "students") {
      renderStudentDirectory();
      return;
    }
    if (state.activeTab === "requests") {
      renderRequestDirectory();
      return;
    }
    renderManagerDirectory();
  }

  function syncTabButtons() {
    document.querySelectorAll("[data-tab]").forEach((node) => {
      node.classList.toggle("is-active", node.dataset.tab === state.activeTab);
    });
  }

  function renderTabCounts() {
    const managers = state.data?.managers || {};
    const teachers = state.data?.teachers || {};
    const students = state.data?.students || {};
    const requests = state.data?.requests || {};

    if (el("tab-count-manager")) {
      el("tab-count-manager").textContent = `${formatInteger(managers.total_count || 0)} manager`;
    }
    if (el("tab-count-teachers")) {
      el("tab-count-teachers").textContent = `${formatInteger(teachers.total_count || 0)} ustoz`;
    }
    if (el("tab-count-students")) {
      el("tab-count-students").textContent = `${formatInteger(students.total || 0)} o'quvchi`;
    }
    if (el("tab-count-products")) {
      el("tab-count-products").textContent = `${formatInteger(requests.products_count || 0)} mahsulot`;
    }
    if (el("tab-count-requests")) {
      el("tab-count-requests").textContent = `${formatInteger(requests.all_requests_count || 0)} so'rov`;
    }
  }

  function ensureChart(key, canvasId, buildConfig) {
    const canvas = el(canvasId);
    if (!canvas || !window.Chart) return null;
    if (!state.charts[key]) {
      state.charts[key] = new Chart(canvas.getContext("2d"), buildConfig());
    }
    return state.charts[key];
  }

  function buildLeadPulse() {
    const marketing = state.data?.marketing || {};
    const funnel = marketing.funnel || [];
    const contacted = funnel[1]?.count || 0;
    const paid = marketing.paid_students || 0;
    const active = marketing.active_students || 0;
    const previous = marketing.total_leads_previous || 0;
    const total = marketing.total_leads || 0;

    const chart = ensureChart("leadPulse", "lead-pulse-chart", () => ({
      type: "doughnut",
      data: { labels: [], datasets: [{ data: [], backgroundColor: [] }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "70%",
        plugins: { legend: { display: false } },
      },
    }));

    if (chart) {
      chart.data.labels = ["Bog'lanildi", "To'lov qilgan", "Faol o'quvchi"];
      chart.data.datasets[0].data = [contacted, paid, active];
      chart.data.datasets[0].backgroundColor = [COLORS.cyan, COLORS.amber, COLORS.emerald];
      chart.update();
    }

    if (el("lead-growth-chip")) {
      el("lead-growth-chip").className = `chip ${toneClassByValue(marketing.conversion_growth)}`;
      el("lead-growth-chip").textContent = signedPct(marketing.conversion_growth);
    }
    if (el("lead-pulse-total")) el("lead-pulse-total").textContent = formatInteger(total);
    if (el("lead-pulse-meta")) {
      el("lead-pulse-meta").innerHTML = [
        stackRow("Umumiy lead bazasi", "Markaz bo'yicha barcha to'plangan leadlar", formatInteger(marketing.all_time_leads || 0), COLORS.cyan),
        stackRow("Oldingi davr", "Taqqoslash uchun oldingi davr leadlari", formatInteger(previous), COLORS.slate),
        stackRow("Eng yaxshi manba", marketing.best_source?.name || "Manba topilmadi", marketing.best_source ? displayPct(marketing.best_source.conversion) : "-", COLORS.amber),
        stackRow("Faolga aylanish", "Leadlardan faol o'quvchigacha", displayPct(marketing.active_conversion_rate), COLORS.emerald),
      ].join("");
    }
  }

  function buildKpis() {
    const finance = state.data?.finance || {};
    const students = state.data?.students || {};
    const charts = state.data?.charts || {};
    const churnSummary = state.ai?.churn?.summary || {};
    const churnItems = state.ai?.churn?.items || [];
    const items = [
      {
        id: "income",
        key: "daromad",
        label: "Daromad",
        value: compactMoney(finance.income || 0),
        delta: finance.income_growth || 0,
        color: COLORS.cyan,
        spark: charts.income || [],
        labels: charts.labels || [],
        sub: `Oldingi davr: ${compactMoney(finance.income_previous || 0)}`,
      },
      {
        id: "profit",
        key: "foyda",
        label: "Foyda",
        value: compactMoney(finance.profit || 0),
        delta: finance.profit_growth || 0,
        color: COLORS.emerald,
        spark: charts.cashflow || [],
        labels: charts.labels || [],
        sub: `Marja ${displayPct(finance.profit_margin || 0)}`,
      },
      {
        id: "expense",
        key: "xarajat",
        label: "Xarajat",
        value: compactMoney(finance.expense || 0),
        delta: finance.expense_growth || 0,
        color: COLORS.amber,
        spark: charts.expenses || [],
        labels: charts.labels || [],
        sub: `Operatsion: ${compactMoney(finance.operating_expense || 0)}`,
      },
      {
        id: "debt",
        key: "qarz",
        label: "Qarz",
        value: compactMoney(finance.open_debt || 0),
        delta: -(finance.debt_ratio || 0),
        color: COLORS.rose,
        spark: charts.debt_series || [],
        labels: charts.labels || [],
        sub: `${formatInteger(finance.debtors_count || 0)} qarzdor`,
      },
      {
        id: "students",
        key: "faol",
        label: "Faol o'quvchi",
        value: `${formatInteger(students.active_students || 0)} kishi`,
        delta: students.growth_pct || 0,
        color: COLORS.violet,
        spark: charts.income_students || charts.new_students || [],
        labels: charts.labels || [],
        sub: `Yangi ${formatInteger(students.new_count || 0)} ta`,
      },
    ];

    if (Object.keys(churnSummary).length) {
      items.push({
        id: "churn",
        key: "risk",
        label: "Chiqish xavfi",
        value: `${formatInteger(churnSummary.danger || 0)} ta`,
        delta: 0,
        badgeText: `${formatInteger(churnSummary.watch || 0)} kuzatuv`,
        deltaText: `O'rtacha risk ${formatInteger(churnSummary.average_score || 0)} ball`,
        color: COLORS.rose,
        spark: churnItems.map((item) => Number(item.score || 0)),
        labels: churnItems.map((item) => item.student_name || ""),
        sub: `${formatInteger(churnSummary.good || 0)} yaxshi holatda`,
      });
    }

    return items;
  }

  function iconSvg(key) {
    const map = {
      daromad: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
      foyda: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
      xarajat: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg>',
      qarz: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
      faol: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
      risk: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/></svg>',
      konv: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="19" y1="5" x2="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></svg>',
    };
    return map[key] || map.konv;
  }

  function getModalDetailTarget(item) {
    if (!item) return null;
    if (item.key === "daromad" && config.paymentsUrl) {
      return {
        type: "url",
        url: config.paymentsUrl,
        title: "To'lovlar bo'limi",
        buttonText: "To'lovlarga o'tish",
      };
    }
    if (item.key === "foyda" && config.paymentsUrl) {
      return {
        type: "url",
        url: config.paymentsUrl,
        title: "Moliya bo'limi",
        buttonText: "Moliyaga o'tish",
      };
    }
    if (item.key === "xarajat" && config.expensesUrl) {
      return {
        type: "url",
        url: config.expensesUrl,
        title: "Xarajatlar bo'limi",
        buttonText: "Xarajatlarga o'tish",
      };
    }
    if (item.key === "qarz" && config.debtorsUrl) {
      return {
        type: "url",
        url: config.debtorsUrl,
        title: "Qarzdorlar bo'limi",
        buttonText: "Qarzdorlarga o'tish",
      };
    }
    if (item.key === "faol" && config.studentsUrl) {
      return {
        type: "url",
        url: config.studentsUrl,
        title: "O'quvchilar bo'limi",
        buttonText: "O'quvchilarga o'tish",
      };
    }
    if (item.key === "risk" && config.studentsUrl) {
      return {
        type: "url",
        url: config.studentsUrl,
        title: "Riskdagi o'quvchilar",
        buttonText: "O'quvchilarga o'tish",
      };
    }
    return null;
  }

  function pulseSection(node, color = COLORS.cyan) {
    if (!node) return;
    const previousTransition = node.style.transition;
    const previousBoxShadow = node.style.boxShadow;
    const previousBorderColor = node.style.borderColor;
    node.style.transition = "box-shadow .35s ease, border-color .35s ease";
    node.style.boxShadow = previousBoxShadow
      ? `0 0 0 1px ${color}44, 0 0 0 8px ${color}12, ${previousBoxShadow}`
      : `0 0 0 1px ${color}44, 0 0 0 8px ${color}12`;
    node.style.borderColor = `${color}66`;
    window.setTimeout(() => {
      node.style.boxShadow = previousBoxShadow;
      node.style.borderColor = previousBorderColor;
      node.style.transition = previousTransition;
    }, 1500);
  }

  function openModalDetail() {
    const target = state.modalDetailTarget;
    if (!target) return;
    closeModal();
    if (target.type === "url" && target.url) {
      window.location.href = target.url;
    }
  }

  function renderKpis() {
    const items = buildKpis();
    const grid = el("kpi-grid");
    if (!grid) return;
    state.kpiSeries = {};
    grid.innerHTML = items.map((item, index) => {
      state.kpiSeries[item.id] = item;
      return `
        <div class="glass kpi-card" data-kpi-id="${escapeHtml(item.id)}" style="border-radius:18px;padding:15px;display:flex;flex-direction:column;gap:9px;animation:fadeIn .4s ease ${index * 0.06}s both;">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,${item.color},transparent);opacity:.72;border-radius:2px 2px 0 0;"></div>
          <div style="position:absolute;top:-28px;right:-28px;width:76px;height:76px;background:radial-gradient(circle,${item.color}1f 0%,transparent 70%);pointer-events:none;"></div>
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:7px;">
            <div style="display:flex;align-items:center;gap:7px;">
              <div style="width:31px;height:31px;border-radius:9px;display:flex;align-items:center;justify-content:center;background:${item.color}1a;border:1px solid ${item.color}28;color:${item.color};flex-shrink:0;">${iconSvg(item.key)}</div>
              <span style="font-size:.66rem;font-weight:700;color:rgba(255,255,255,.44);text-transform:uppercase;letter-spacing:.04em;line-height:1.3;">${escapeHtml(item.label)}</span>
            </div>
            <span class="chip ${item.badgeText ? "cn" : toneClassByValue(item.delta)}" style="flex-shrink:0;">${escapeHtml(item.badgeText || signedPct(item.delta))}</span>
          </div>
          <div>
            <div style="font-size:1.22rem;font-weight:800;color:#f1f5f9;letter-spacing:-.01em;line-height:1.1;">${escapeHtml(item.value)}</div>
            <div style="font-size:.65rem;color:rgba(255,255,255,.35);margin-top:2px;">${escapeHtml(item.sub)}</div>
          </div>
          <div style="height:40px;margin-top:auto;"><canvas id="spark-${escapeHtml(item.id)}"></canvas></div>
        </div>
      `;
    }).join("");

    Object.values(state.sparkCharts).forEach((chart) => chart.destroy());
    state.sparkCharts = {};

    items.forEach((item) => {
      const canvas = el(`spark-${item.id}`);
      if (!canvas || !window.Chart) return;
      state.sparkCharts[item.id] = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
          labels: item.labels || [],
          datasets: [{
            data: item.spark || [],
            borderColor: item.color,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.42,
            fill: true,
            backgroundColor(context) {
              const gradient = context.chart.ctx.createLinearGradient(0, 0, 0, context.chart.height);
              gradient.addColorStop(0, `${item.color}55`);
              gradient.addColorStop(1, `${item.color}00`);
              return gradient;
            },
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { enabled: false } },
          scales: { x: { display: false }, y: { display: false } },
        },
      });
    });

    grid.querySelectorAll("[data-kpi-id]").forEach((card) => {
      card.addEventListener("click", () => {
        const item = state.kpiSeries[card.dataset.kpiId];
        if (item) openModal(item);
      });
    });
  }

  function renderRevenueChart() {
    const charts = state.data?.charts || {};
    const series = [
      { key: "income", label: "Daromad", color: COLORS.cyan, data: charts.income || [] },
      { key: "expenses", label: "Xarajat", color: COLORS.amber, data: charts.expenses || [] },
      { key: "cashflow", label: "Pul oqimi", color: COLORS.emerald, data: charts.cashflow || [] },
      { key: "debt", label: "Qarzdorlik", color: COLORS.rose, data: charts.debt_series || [] },
    ];

    const legend = el("rev-legend");
    if (legend) {
      legend.innerHTML = series.map((item) => {
        const active = !!state.seriesVisible[item.key];
        return `
          <button type="button" data-series-key="${escapeHtml(item.key)}" style="display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:8px;border:1px solid ${active ? `${item.color}30` : "rgba(255,255,255,.06)"};background:${active ? `${item.color}12` : "rgba(255,255,255,.03)"};color:${active ? item.color : "rgba(255,255,255,.33)"};font-size:.7rem;font-weight:700;opacity:${active ? 1 : .42};transition:all .2s;cursor:pointer;">
            <div style="width:8px;height:8px;border-radius:50%;background:${item.color};"></div>${escapeHtml(item.label)}
          </button>
        `;
      }).join("");
      legend.querySelectorAll("[data-series-key]").forEach((button) => {
        button.addEventListener("click", () => {
          const key = button.dataset.seriesKey;
          const visibleCount = Object.values(state.seriesVisible).filter(Boolean).length;
          if (visibleCount === 1 && state.seriesVisible[key]) return;
          state.seriesVisible[key] = !state.seriesVisible[key];
          renderRevenueChart();
        });
      });
    }

    const chart = ensureChart("revenue", "rev-chart", () => ({
      type: "line",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title(items) {
                const label = items?.[0]?.label;
                return formatApiDate(label, { includeYear: true });
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: "rgba(255,255,255,.04)", drawBorder: false },
            ticks: {
              color: "rgba(255,255,255,.3)",
              font: { size: 10 },
              autoSkip: false,
              maxRotation: 0,
              minRotation: 0,
              callback(value) {
                return formatApiDate(this.getLabelForValue(value), { includeYear: false, multiline: true });
              },
            },
          },
          y: {
            grid: { color: "rgba(255,255,255,.04)", drawBorder: false },
            ticks: {
              color: "rgba(255,255,255,.25)",
              font: { size: 10 },
              callback(value) { return compactNumber(value); },
            },
          },
        },
      },
    }));

    if (chart) {
      chart.data.labels = charts.labels || [];
      chart.data.datasets = series.map((item) => ({
        label: item.label,
        data: item.data,
        borderColor: item.color,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.42,
        hidden: !state.seriesVisible[item.key],
        fill: item.key === "income" || item.key === "expenses",
        backgroundColor(context) {
          const gradient = context.chart.ctx.createLinearGradient(0, 0, 0, context.chart.height);
          gradient.addColorStop(0, `${item.color}22`);
          gradient.addColorStop(1, `${item.color}00`);
          return gradient;
        },
      }));
      chart.update();
    }
  }

  function renderPaymentBlock() {
    const finance = state.data?.finance || {};
    const done = Number(finance.payment_completion_rate || 0);
    const overdue = finance.billed_students_count ? percentOf(finance.debtors_count || 0, finance.billed_students_count || 1) : 0;
    const pending = Math.max(0, 100 - done - overdue);

    const chart = ensureChart("payment", "donut-chart", () => ({
      type: "doughnut",
      data: { labels: [], datasets: [{ data: [], backgroundColor: [] }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: { legend: { display: false } },
      },
    }));

    if (chart) {
      chart.data.labels = ["To'landi", "Kutilmoqda", "Muddati o'tgan"];
      chart.data.datasets[0].data = [done, pending, overdue];
      chart.data.datasets[0].backgroundColor = [COLORS.emerald, COLORS.cyan, COLORS.rose];
      chart.update();
    }

    if (el("donut-pct")) el("donut-pct").textContent = `${Math.round(done)}%`;
    if (el("pay-prog")) el("pay-prog").style.width = `${Math.max(0, Math.min(done, 100))}%`;

    const legend = el("pay-legend");
    if (legend) {
      const rows = [
        ["To'landi", done, COLORS.emerald],
        ["Kutilmoqda", pending, COLORS.cyan],
        ["Muddati o'tgan", overdue, COLORS.rose],
      ];
      legend.innerHTML = rows.map(([label, value, color]) => `
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <div style="display:flex;align-items:center;gap:7px;">
            <div style="width:7px;height:7px;border-radius:50%;background:${color};box-shadow:0 0 6px ${color};flex-shrink:0;"></div>
            <span style="font-size:.7rem;color:rgba(255,255,255,.48);">${escapeHtml(label)}</span>
          </div>
          <span style="font-size:.76rem;font-weight:700;color:${color};">${displayPct(value)}</span>
        </div>
      `).join("");
    }

    if (el("m-ortacha")) el("m-ortacha").textContent = compactMoney(finance.avg_payment || 0);
    if (el("m-bajarildi")) el("m-bajarildi").textContent = `${formatInteger(finance.paid_students_count || 0)}/${formatInteger(finance.billed_students_count || 0)}`;
    if (el("m-sifat")) el("m-sifat").textContent = displayPct(finance.income_quality_score || 0);
    if (el("m-qayta")) el("m-qayta").textContent = displayPct(finance.recurring_share || 0);
    if (el("m-total")) el("m-total").textContent = compactMoney(finance.income || 0);
  }

  function renderFunnelInto(targetId, funnel) {
    const wrap = el(targetId);
    if (!wrap) return;
    if (!funnel.length) {
      wrap.innerHTML = '<div class="loading-shell">Lead voronkasi topilmadi.</div>';
      return;
    }
    const colors = [COLORS.cyan, COLORS.violet, COLORS.amber, COLORS.emerald, COLORS.rose, COLORS.amber];
    const maxCount = funnel[0].count || 1;
    wrap.innerHTML = funnel.map((item, index) => {
      const color = colors[index % colors.length];
      const width = Math.max(14, Math.round(percentOf(item.count || 0, maxCount)));
      const pct = percentOf(item.count || 0, maxCount);
      return `
        <div>
          <div style="display:flex;align-items:center;gap:9px;">
            <div style="min-width:96px;font-size:.69rem;color:rgba(255,255,255,.44);font-weight:500;text-align:right;">${escapeHtml(item.stage)}</div>
            <div style="flex:1;">
              <div style="width:${width}%;height:30px;border-radius:8px;display:flex;align-items:center;padding:0 10px;background:linear-gradient(90deg,${color}22,${color}12);border:1px solid ${color}24;">
                <div style="width:5px;height:5px;border-radius:50%;background:${color};box-shadow:0 0 6px ${color};flex-shrink:0;"></div>
                <span style="margin-left:7px;font-size:.77rem;font-weight:700;color:${color};">${formatInteger(item.count || 0)}</span>
                <span style="margin-left:3px;font-size:.62rem;color:${color};opacity:.65;">kishi</span>
              </div>
            </div>
            <div class="chip" style="flex-shrink:0;min-width:48px;justify-content:center;background:${color}14;color:${color};">${Math.round(pct)}%</div>
          </div>
        </div>
      `;
    }).join("");
  }

  function renderLeadAnalyticsPanel() {
    const marketing = state.data?.marketing || {};
    const sources = Array.isArray(marketing.sources_overall) && marketing.sources_overall.length
      ? [...marketing.sources_overall]
      : (Array.isArray(marketing.sources) ? [...marketing.sources] : []);
    const directions = Array.isArray(marketing.directions_overall) && marketing.directions_overall.length
      ? [...marketing.directions_overall]
      : (Array.isArray(marketing.directions) ? [...marketing.directions] : []);
    const wrap = el("goals-wrap");
    if (!wrap) return;

    if (state.charts.leadAnalytics) {
      state.charts.leadAnalytics.destroy();
      state.charts.leadAnalytics = null;
    }

    const palette = [COLORS.emerald, COLORS.cyan, COLORS.amber, COLORS.violet, COLORS.rose];
    const sortedSources = sources.sort((left, right) => {
      const leadDiff = Number(right.count || 0) - Number(left.count || 0);
      if (leadDiff !== 0) return leadDiff;
      const studentDiff = Number(right.converted_students || 0) - Number(left.converted_students || 0);
      if (studentDiff !== 0) return studentDiff;
      return Number(right.active_students || 0) - Number(left.active_students || 0);
    });
    const sortedDirections = directions.sort((left, right) => {
      const leadDiff = Number(right.count || 0) - Number(left.count || 0);
      if (leadDiff !== 0) return leadDiff;
      const studentDiff = Number(right.converted_students || 0) - Number(left.converted_students || 0);
      if (studentDiff !== 0) return studentDiff;
      return Number(right.active_students || 0) - Number(left.active_students || 0);
    });

    const totalSourceLeads = sortedSources.reduce((sum, item) => sum + Number(item.count || 0), 0);
    const totalDirectionLeads = sortedDirections.reduce((sum, item) => sum + Number(item.count || 0), 0);
    const topSource = sortedSources[0] || null;
    const topDirection = sortedDirections[0] || null;
    const topSourceShare = topSource ? percentOf(topSource.count || 0, totalSourceLeads || 1) : 0;

    const visibleSources = sortedSources.slice(0, 4);
    const remainingSources = sortedSources.slice(4);
    const remainingMetricTotal = remainingSources.reduce((sum, item) => sum + Number(item.count || 0), 0);
    const chartRows = visibleSources.map((item) => ({
      name: item.name || "Noma'lum",
      value: Number(item.count || 0),
    }));
    if (remainingMetricTotal > 0) {
      chartRows.push({ name: "Boshqalar", value: remainingMetricTotal });
    }

    const totalLeads = Number(marketing.all_time_leads || totalSourceLeads || marketing.total_leads || 0);
    const currentPeriodLeads = Number(marketing.total_leads || 0);
    const previousPeriodLeads = Number(marketing.total_leads_previous || 0);
    const convertedStudents = Number(marketing.all_time_converted_students || 0);
    const activeStudents = Number(marketing.all_time_active_students || 0);
    const studentConversionRate = totalLeads > 0 ? percentOf(convertedStudents, totalLeads) : 0;
    const activeShareRate = totalLeads > 0 ? percentOf(activeStudents, totalLeads) : 0;

    const summaryItems = [
      {
        label: "Jami lead",
        value: formatInteger(totalLeads),
        sub: "Bazadagi barcha leadlar",
        color: COLORS.amber,
      },
      {
        label: "Bu davr leadi",
        value: formatInteger(currentPeriodLeads),
        sub: `${formatInteger(previousPeriodLeads)} oldingi davr`,
        color: COLORS.cyan,
      },
      {
        label: "O'quvchiga aylangan",
        value: formatInteger(convertedStudents),
        sub: `${displayPct(studentConversionRate)} umumiy konversiya`,
        color: COLORS.emerald,
      },
      {
        label: "Faol o'quvchi",
        value: formatInteger(activeStudents),
        sub: `${displayPct(activeShareRate)} faol ulushi`,
        color: COLORS.violet,
      },
    ];

    const sourcesHtml = visibleSources.length ? visibleSources.map((item, index) => {
      const share = totalSourceLeads > 0 ? percentOf(item.count || 0, totalSourceLeads) : 0;
      const color = palette[index % palette.length];
      return `
        <div class="stack-item" style="border-color:${color}22;background:linear-gradient(135deg, ${color}10, rgba(255,255,255,.02));">
          <div>
            <strong style="display:flex;align-items:center;gap:8px;">
              <span style="width:8px;height:8px;border-radius:50%;background:${color};box-shadow:0 0 8px ${color};display:inline-block;"></span>
              ${escapeHtml(item.name || "Noma'lum")}
            </strong>
            <small>${formatInteger(item.count || 0)} lead · ${formatInteger(item.converted_students || 0)} o'quvchi · ${formatInteger(item.active_students || 0)} faol</small>
          </div>
          <div class="tail" style="color:${color};">${Math.round(share)}%</div>
        </div>
      `;
    }).join("") : '<div class="loading-shell" style="min-height:90px;">Lead manbalari topilmadi.</div>';

    const directionsHtml = sortedDirections.length ? sortedDirections.slice(0, 4).map((item, index) => {
      const share = totalDirectionLeads > 0 ? percentOf(item.count || 0, totalDirectionLeads) : 0;
      const color = palette[index % palette.length];
      return `
        <div style="padding:10px 12px;border-radius:12px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px;">
            <strong style="font-size:.8rem;color:${COLORS.white};">${escapeHtml(item.name || "Yo'nalishsiz")}</strong>
            <span class="chip" style="background:${color}18;color:${color};">${formatInteger(item.active_students || item.converted_students || item.count || 0)} o'quvchi</span>
          </div>
          <div class="pt" style="height:6px;border-radius:999px;">
            <div class="pf" style="width:${share}%;border-radius:999px;background:linear-gradient(90deg, ${color}, ${COLORS.white}22);box-shadow:0 0 10px ${color}40;"></div>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:6px;font-size:.66rem;">
            <span style="color:rgba(255,255,255,.38);">${formatInteger(item.count || 0)} lead · ${formatInteger(item.converted_students || 0)} o'quvchi · ${displayPct(item.student_conversion || 0)} conv</span>
            <span style="color:${color};font-weight:700;">${Math.round(share)}% ulush</span>
          </div>
        </div>
      `;
    }).join("") : '<div class="loading-shell" style="min-height:80px;">Yo\'nalish ma\'lumoti topilmadi.</div>';

    const note = topSource && topDirection
      ? `${topSource.name} manbasi ${formatInteger(topSource.count || 0)} lead bilan yetakchi. Undan ${formatInteger(topSource.converted_students || 0)} tasi o'quvchiga, ${formatInteger(topSource.active_students || 0)} tasi faolga aylangan. ${topDirection.name} yo'nalishi esa ${formatInteger(topDirection.count || 0)} lead bilan oldinda.`
      : topSource
        ? `${topSource.name} manbasi hozir eng kuchli kanal bo'lib turibdi.`
        : "Lead statistikasi uchun hozircha yetarli ma'lumot topilmadi.";

    wrap.innerHTML = `
      <div class="ring-area" style="grid-template-columns:148px 1fr;align-items:center;">
        <div class="ring-shell" style="width:138px;height:138px;">
          <canvas id="lead-goals-chart"></canvas>
          <div class="ring-overlay">
            <strong style="color:${topSource ? COLORS.cyan : COLORS.slate};">${Math.round(topSourceShare)}%</strong>
            <span style="margin-top:6px;font-size:.58rem;letter-spacing:0;text-transform:none;max-width:86px;line-height:1.3;">${escapeHtml(topSource?.name || "Lead oqimi")}</span>
            <small style="margin-top:4px;font-size:.58rem;color:rgba(255,255,255,.45);">${formatInteger(topSource?.count || totalLeads)} lead</small>
          </div>
        </div>
        <div class="stack-list">${sourcesHtml}</div>
      </div>
      <div class="summary-grid" style="grid-template-columns:repeat(2,minmax(0,1fr));">
        ${summaryItems.map((item) => `
          <div class="summary-tile" style="background:${item.color}10;border-color:${item.color}26;">
            <span class="label">${escapeHtml(item.label)}</span>
            <div class="value" style="color:${item.color};">${escapeHtml(item.value)}</div>
            <div class="sub">${escapeHtml(item.sub)}</div>
          </div>
        `).join("")}
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;">
        <div class="slbl">YO'NALISHLAR BO'YICHA</div>
        <span class="chip cn" style="background:rgba(99,102,241,.14);color:${COLORS.violet};">${formatInteger(directions.length)} yo'nalish</span>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px;">${directionsHtml}</div>
      <div class="panel-note">${escapeHtml(note)}</div>
    `;

    const canvas = el("lead-goals-chart");
    if (!canvas || !window.Chart) return;
    state.charts.leadAnalytics = new Chart(canvas.getContext("2d"), {
      type: "doughnut",
      data: {
        labels: chartRows.map((item) => item.name),
        datasets: [{
          data: chartRows.map((item) => item.value),
          backgroundColor: chartRows.map((_, index) => palette[index % palette.length]),
          borderColor: "#0f172a",
          borderWidth: 4,
          hoverOffset: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "72%",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label(context) {
                const value = Number(context.raw || 0);
                const share = chartRows.reduce((sum, item) => sum + Number(item.value || 0), 0) > 0
                  ? percentOf(value, chartRows.reduce((sum, item) => sum + Number(item.value || 0), 0))
                  : 0;
                return `${context.label}: ${formatInteger(value)} lead (${Math.round(share)}%)`;
              },
            },
          },
        },
      },
    });
  }

  function toneColor(tone) {
    if (tone === "warning" || tone === "amber") return COLORS.amber;
    if (tone === "success" || tone === "emerald") return COLORS.emerald;
    if (tone === "rose" || tone === "danger") return COLORS.rose;
    if (tone === "violet") return COLORS.violet;
    return COLORS.cyan;
  }

  function renderAiLoading() {
    state.ai.insights = [];
    state.ai.churn = { items: [], summary: {} };
    state.ai.forecast = { items: [], summary: {} };
    const insightNode = el("ai-insights-list");
    if (insightNode) {
      insightNode.innerHTML = '<div class="loading-shell" style="min-height:180px;">AI tahlil yuklanmoqda...</div>';
    }
    const churnNode = el("churn-risk-list");
    if (churnNode) {
      churnNode.innerHTML = '<div class="loading-shell" style="min-height:140px;">Xavfli o\'quvchilar hisoblanmoqda...</div>';
    }
    if (el("forecastSummaryNote")) {
      el("forecastSummaryNote").textContent = "Weighted moving average asosida prognoz hisoblanmoqda...";
    }
    if (el("forecastNextAmount")) el("forecastNextAmount").textContent = "0 UZS";
    setChipState("aiInsightsMeta", "Yuklanmoqda...", "cn");
    setChipState("churnSummaryChip", "Yuklanmoqda...", "cn");
    setChipState("forecastMetaChip", "Yuklanmoqda...", "cn");
  }

  function renderAiInsightsPanel(payload) {
    const items = payload?.insights || [];
    state.ai.insights = items;
    const node = el("ai-insights-list");
    if (!node) return;
    if (!items.length) {
      node.innerHTML = '<div class="loading-shell" style="min-height:180px;">AI insight topilmadi. Fallback xulosalar kutilyapti.</div>';
      setChipState("aiInsightsMeta", "AI ma'lumoti yo'q", "cy");
      return;
    }
    node.innerHTML = items.map((item) => {
      const color = toneColor(item.type);
      const chipTone = item.type === "success" ? "cg" : item.type === "warning" ? "cy" : "cc";
      return `
        <div class="ai-insight-item">
          <strong>
            <span class="ai-dot" style="background:${color};box-shadow:0 0 8px ${color};"></span>
            ${escapeHtml(item.title || "AI insight")}
            <span class="chip ${chipTone}" style="margin-left:auto;">${escapeHtml(item.type === "success" ? "Ijobiy" : item.type === "warning" ? "Ogoh" : "Ma'lumot")}</span>
          </strong>
          <p>${escapeHtml(item.text || "")}</p>
        </div>
      `;
    }).join("");
    const sourceTone = payload?.source === "gemini" || payload?.source === "cache" ? "cc" : "cy";
    const sourceLabel = payload?.source === "gemini" || payload?.source === "cache" ? "Gemini / cache" : "Fallback";
    setChipState("aiInsightsMeta", `${sourceLabel} · ${payload?.generated_at || "tayyor"}`, sourceTone);
  }

  function renderChurnRiskWidget(payload) {
    const items = payload?.items || [];
    const summary = payload?.summary || {};
    state.ai.churn = { items, summary };

    if (el("churnDangerCount")) el("churnDangerCount").textContent = formatInteger(summary.danger || 0);
    if (el("churnWatchCount")) el("churnWatchCount").textContent = formatInteger(summary.watch || 0);
    if (el("churnGoodCount")) el("churnGoodCount").textContent = formatInteger(summary.good || 0);
    if (el("churnAverageScore")) el("churnAverageScore").textContent = formatInteger(summary.average_score || 0);
    setChipState(
      "churnSummaryChip",
      `${formatInteger(summary.danger || 0)} xavfli · ${formatInteger(summary.watch || 0)} kuzatuv`,
      Number(summary.danger || 0) > 0 ? "cr" : Number(summary.watch || 0) > 0 ? "cy" : "cg"
    );

    const node = el("churn-risk-list");
    if (!node) return;
    if (!items.length) {
      node.innerHTML = '<div class="loading-shell" style="min-height:120px;">Xavfli o\'quvchi topilmadi.</div>';
      renderKpis();
      return;
    }
    node.innerHTML = items.map((item) => {
      const toneClass = item.tone === "rose" ? "cr" : item.tone === "amber" ? "cy" : "cg";
      const color = toneColor(item.tone);
      const groups = (item.groups || []).length ? item.groups.join(", ") : "Guruh birikmagan";
      const reasonText = (item.reasons || []).join(" · ");
      return `
        <div class="churn-row" style="border-color:${color}22;background:linear-gradient(135deg, ${color}10, rgba(255,255,255,.02));">
          <div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <strong>${escapeHtml(item.student_name || "O'quvchi")}</strong>
              <span class="chip ${toneClass}">${formatInteger(item.score || 0)} ball · ${escapeHtml(item.status || "Holat")}</span>
            </div>
            <p>${escapeHtml(groups)}</p>
            <p>${escapeHtml(reasonText || "Holat barqaror")}</p>
          </div>
          <div class="churn-actions">
            <span class="chip cn">${formatInteger(item.overdue_months || 0)} oy qarz</span>
            ${item.call_url
              ? `<a class="call-btn" href="${escapeHtml(item.call_url)}"><i class="fa-solid fa-phone-volume"></i>Qo'ng'iroq</a>`
              : `<span class="chip cn">Telefon yo'q</span>`}
          </div>
        </div>
      `;
    }).join("");
    renderKpis();
  }

  function renderForecastChart(payload) {
    const items = payload?.items || [];
    const summary = payload?.summary || {};
    state.ai.forecast = { items, summary };
    if (el("forecastNextAmount")) el("forecastNextAmount").textContent = compactMoney(summary.next_month_amount || 0);
    if (el("forecastSummaryNote")) {
      el("forecastSummaryNote").textContent = `${items.filter((item) => !item.is_forecast).length} oy real ma'lumot va ${items.filter((item) => item.is_forecast).length} oy prognoz oxirgi 3 oy og'irlikli o'rtachasiga tayangan.`;
    }
    setChipState("forecastMetaChip", `${summary.anchor_label || "Joriy oy"} bazasi`, "cy");

    const chart = ensureChart("forecast", "forecast-chart", () => ({
      type: "line",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: "rgba(255,255,255,.48)", usePointStyle: true, boxWidth: 10 } },
          tooltip: {
            backgroundColor: "#08101e",
            titleColor: "#eef4ff",
            bodyColor: "#cbd7ea",
            borderColor: "rgba(255,255,255,0.08)",
            borderWidth: 1,
            padding: 12,
            cornerRadius: 14,
          },
        },
        scales: {
          x: {
            ticks: { color: "rgba(255,255,255,.38)" },
            grid: { color: "rgba(255,255,255,.04)" },
          },
          y: {
            ticks: {
              color: "rgba(255,255,255,.38)",
              callback(value) { return compactNumber(value); },
            },
            grid: { color: "rgba(255,255,255,.04)" },
          },
        },
      },
    }));
    if (!chart) return;

    const firstForecastIndex = items.findIndex((item) => item.is_forecast);
    chart.data.labels = items.map((item) => item.label || item.month);
    chart.data.datasets = [
      {
        label: "Haqiqiy daromad",
        data: items.map((item) => item.is_forecast ? null : Number(item.amount || 0)),
        borderColor: COLORS.cyan,
        backgroundColor(context) {
          const gradient = context.chart.ctx.createLinearGradient(0, 0, 0, context.chart.height);
          gradient.addColorStop(0, `${COLORS.cyan}22`);
          gradient.addColorStop(1, `${COLORS.cyan}00`);
          return gradient;
        },
        fill: true,
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2.5,
      },
      {
        label: "Prognoz",
        data: items.map((item, index) => {
          if (firstForecastIndex === -1) return null;
          if (index < firstForecastIndex - 1) return null;
          if (index === firstForecastIndex - 1) return Number(items[index]?.amount || 0);
          return item.is_forecast ? Number(item.amount || 0) : null;
        }),
        borderColor: COLORS.amber,
        borderDash: [7, 6],
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2.5,
        fill: false,
      },
    ];
    chart.update();
  }

  function scheduleAiRefresh() {
    if (state.aiRefreshTimer) window.clearTimeout(state.aiRefreshTimer);
    state.aiRefreshTimer = window.setTimeout(() => {
      loadAiWidgets({ silent: true });
    }, 30 * 60 * 1000);
  }

  async function loadAiWidgets({ silent = false } = {}) {
    const wantsInsights = Boolean(AI_INSIGHTS_URL && el("ai-insights-list"));
    if (!wantsInsights && !AI_CHURN_URL && !AI_FORECAST_URL) return;
    const token = Date.now();
    state.ai.requestToken = token;
    if (!silent) renderAiLoading();

    const requests = await Promise.allSettled([
      wantsInsights ? fetchJson(AI_INSIGHTS_URL) : Promise.resolve(null),
      AI_CHURN_URL ? fetchJson(AI_CHURN_URL) : Promise.resolve(null),
      AI_FORECAST_URL ? fetchJson(AI_FORECAST_URL) : Promise.resolve(null),
    ]);

    if (state.ai.requestToken !== token) return;

    const [insightsResult, churnResult, forecastResult] = requests;
    if (insightsResult.status === "fulfilled" && insightsResult.value) {
      renderAiInsightsPanel(insightsResult.value);
    } else {
      setChipState("aiInsightsMeta", "Fallback xulosa", "cy");
      const fallbackInsights = (state.data?.insights || []).slice(0, 4).map((item) => ({
        type: item.severity === "critical" || item.severity === "high" ? "warning" : item.severity === "low" ? "success" : "info",
        title: item.title || "Dashboard insight",
        text: item.text || "",
      }));
      renderAiInsightsPanel({ insights: fallbackInsights, source: "fallback", generated_at: nowText() });
    }

    if (churnResult.status === "fulfilled" && churnResult.value) {
      renderChurnRiskWidget(churnResult.value);
    } else {
      renderChurnRiskWidget({ items: [], summary: {} });
      setChipState("churnSummaryChip", "Formula ma'lumoti topilmadi", "cy");
    }

    if (forecastResult.status === "fulfilled" && forecastResult.value) {
      renderForecastChart(forecastResult.value);
    } else {
      setChipState("forecastMetaChip", "Prognoz topilmadi", "cy");
      if (el("forecastSummaryNote")) el("forecastSummaryNote").textContent = "Prognoz ma'lumotini olishda xatolik yuz berdi.";
    }

    scheduleAiRefresh();
  }

  function chatDefaultPosition() {
    const launcher = el("directorAiChatLauncher");
    const width = launcher?.offsetWidth || 68;
    const height = launcher?.offsetHeight || 68;
    return {
      x: Math.max(12, window.innerWidth - width - 28),
      y: Math.max(12, window.innerHeight - height - 30),
    };
  }

  function normalizedChatPosition(rawPosition) {
    const fallback = chatDefaultPosition();
    const launcher = el("directorAiChatLauncher");
    const width = launcher?.offsetWidth || 68;
    const height = launcher?.offsetHeight || 68;
    const x = Number(rawPosition?.x);
    const y = Number(rawPosition?.y);
    return {
      x: clamp(Number.isFinite(x) ? x : fallback.x, 12, Math.max(12, window.innerWidth - width - 12)),
      y: clamp(Number.isFinite(y) ? y : fallback.y, 12, Math.max(12, window.innerHeight - height - 12)),
    };
  }

  function positionChatPanel() {
    const panel = el("directorAiChatPanel");
    const launcher = el("directorAiChatLauncher");
    if (!panel || !launcher || !state.chat.open) return;

    const launcherRect = launcher.getBoundingClientRect();
    const panelWidth = panel.offsetWidth || 390;
    const panelHeight = panel.offsetHeight || 560;
    const gap = 14;

    let left = launcherRect.right - panelWidth;
    left = clamp(left, 12, Math.max(12, window.innerWidth - panelWidth - 12));

    let top = launcherRect.top - panelHeight - gap;
    if (top < 12) {
      top = launcherRect.bottom + gap;
    }
    top = clamp(top, 12, Math.max(12, window.innerHeight - panelHeight - 12));

    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
  }

  function applyChatLauncherPosition(rawPosition, { persist = false } = {}) {
    const launcher = el("directorAiChatLauncher");
    if (!launcher) return;
    const next = normalizedChatPosition(rawPosition);
    state.chat.position = next;
    launcher.style.left = `${next.x}px`;
    launcher.style.top = `${next.y}px`;
    positionChatPanel();
    if (persist) persistChatPosition();
  }

  function setChatStatus(text, tone = "cn") {
    setChipState("directorAiChatStatus", text, tone);
  }

  function renderChatMessages() {
    const container = el("directorAiChatMessages");
    if (!container) return;
    const messages = state.chat.messages || [];
    if (!messages.length) {
      container.innerHTML = `
        <div id="directorAiChatEmpty" class="director-ai-chat-empty">
          Masalan shunday yozishingiz mumkin: “Eng qarzdor guruh qaysi?”, “Qaysi lead manbasi yaxshi ishlayapti?”, “Eng kuchli ustoz kim?”.
        </div>
      `;
      return;
    }
    container.innerHTML = messages.map((item) => {
      const role = item.role === "user" ? "user" : "assistant";
      const avatarLabel = role === "user" ? escapeHtml(CURRENT_USER_INITIAL) : "AI";
      const metaLabel = role === "user"
        ? `Siz · ${escapeHtml(item.created_label || formatChatTime(item.created_at))}`
        : `${escapeHtml(item.source === "gemini" || item.source === "cache" ? "AI" : "Dashboard AI")} · ${escapeHtml(item.created_label || formatChatTime(item.created_at))}`;
      return `
        <div class="director-ai-chat-row ${role}">
          ${role === "assistant" ? `<div class="director-ai-chat-avatar assistant">${avatarLabel}</div>` : ""}
          <div class="director-ai-chat-bubble ${role} ${item.loading ? "loading" : ""}">
            ${escapeHtml(item.content || "")}
            <div class="director-ai-chat-meta">${metaLabel}</div>
          </div>
          ${role === "user" ? `<div class="director-ai-chat-avatar user">${avatarLabel}</div>` : ""}
        </div>
      `;
    }).join("");
    container.scrollTop = container.scrollHeight;
    positionChatPanel();
  }

  async function loadChatSession() {
    if (!AI_CHAT_URL) return;
    state.chat.loading = true;
    setChatStatus("Chat yuklanmoqda...", "cc");
    try {
      const payload = await fetchJson(AI_CHAT_URL);
      state.chat.session = payload.session || null;
      state.chat.messages = Array.isArray(payload.messages) ? payload.messages : [];
      state.chat.initialized = true;
      applyChatLauncherPosition(payload.session?.launcher_position);
      renderChatMessages();
      setChatStatus("Tarix saqlandi", "cg");
    } catch (error) {
      console.error(error);
      state.chat.initialized = true;
      state.chat.messages = [];
      applyChatLauncherPosition(state.chat.position);
      renderChatMessages();
      setChatStatus("Chat vaqtincha yuklanmadi", "cy");
    } finally {
      state.chat.loading = false;
      positionChatPanel();
    }
  }

  async function resetChatSession() {
    if (!AI_CHAT_RESET_URL || state.chat.loading) return;
    state.chat.loading = true;
    setChatStatus("Chat tozalanmoqda...", "cc");
    try {
      const response = await fetch(buildUrl(AI_CHAT_RESET_URL), {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ reset: true }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      state.chat.session = payload.session || null;
      state.chat.messages = [];
      renderChatMessages();
      setChatStatus("Chat tozalandi", "cg");
    } catch (error) {
      console.error(error);
      setChatStatus("Chatni tozalab bo'lmadi", "cy");
    } finally {
      state.chat.loading = false;
    }
  }

  function persistChatPosition() {
    if (!AI_CHAT_POSITION_URL) return;
    fetch(buildUrl(AI_CHAT_POSITION_URL), {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({ position: state.chat.position }),
    }).catch((error) => console.error(error));
  }

  function setChatOpen(isOpen) {
    const panel = el("directorAiChatPanel");
    const launcher = el("directorAiChatLauncher");
    if (!panel || !launcher) return;
    state.chat.open = Boolean(isOpen);
    panel.classList.toggle("open", state.chat.open);
    panel.setAttribute("aria-hidden", state.chat.open ? "false" : "true");
    launcher.setAttribute("aria-expanded", state.chat.open ? "true" : "false");
    if (state.chat.open) {
      positionChatPanel();
      if (!state.chat.initialized) loadChatSession();
      window.setTimeout(() => {
        const input = el("directorAiChatInput");
        if (input) input.focus();
      }, 60);
    }
  }

  function autosizeChatInput() {
    const input = el("directorAiChatInput");
    if (!input) return;
    input.style.height = "auto";
    const nextHeight = Math.min(input.scrollHeight, 108);
    input.style.height = `${Math.max(nextHeight, 56)}px`;
  }

  function startChatDrag(event, source) {
    const launcher = el("directorAiChatLauncher");
    const header = el("directorAiChatHeader");
    if (!launcher) return;
    const rect = launcher.getBoundingClientRect();
    state.chat.dragging = true;
    state.chat.dragMoved = false;
    state.chat.activeDragTarget = source;
    state.chat.dragOffsetX = event.clientX - rect.left;
    state.chat.dragOffsetY = event.clientY - rect.top;
    launcher.classList.add("is-dragging");
    if (header && source === "panel") header.classList.add("is-dragging");
    event.preventDefault();
  }

  function handleChatDragMove(event) {
    if (!state.chat.dragging) return;
    state.chat.dragMoved = true;
    applyChatLauncherPosition({
      x: event.clientX - state.chat.dragOffsetX,
      y: event.clientY - state.chat.dragOffsetY,
    });
  }

  function stopChatDrag() {
    const launcher = el("directorAiChatLauncher");
    const header = el("directorAiChatHeader");
    if (!state.chat.dragging) return;
    state.chat.dragging = false;
    state.chat.suppressToggleUntil = state.chat.dragMoved ? Date.now() + 220 : 0;
    launcher?.classList.remove("is-dragging");
    header?.classList.remove("is-dragging");
    if (state.chat.dragMoved) persistChatPosition();
  }

  async function sendChatQuestion(rawQuestion) {
    const question = String(rawQuestion || "").trim();
    if (!AI_CHAT_ASK_URL || !question || state.chat.loading) return;

    const input = el("directorAiChatInput");
    const localUserId = `local-user-${Date.now()}`;
    const localLoadingId = `local-assistant-${Date.now() + 1}`;
    state.chat.loading = true;
    setChatStatus("AI javob tayyorlamoqda...", "cc");

    state.chat.messages = [
      ...state.chat.messages,
      {
        id: localUserId,
        role: "user",
        content: question,
        created_at: new Date().toISOString(),
        created_label: formatChatTime(new Date().toISOString()),
      },
      {
        id: localLoadingId,
        role: "assistant",
        content: "Savol tahlil qilinmoqda...",
        created_at: new Date().toISOString(),
        created_label: formatChatTime(new Date().toISOString()),
        source: "loading",
        loading: true,
      },
    ];
    renderChatMessages();
    setChatOpen(true);
    if (input) input.value = "";
    autosizeChatInput();

    try {
      const response = await fetch(buildUrl(AI_CHAT_ASK_URL), {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ question }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      state.chat.session = payload.session || state.chat.session;
      state.chat.messages = state.chat.messages.filter((item) => item.id !== localLoadingId && item.id !== localUserId);
      if (payload.user_message) state.chat.messages.push(payload.user_message);
      if (payload.assistant_message) {
        state.chat.messages.push(payload.assistant_message);
      } else {
        state.chat.messages.push({
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: payload.answer || "Javob topilmadi.",
          source: payload.source || "fallback",
          created_at: new Date().toISOString(),
          created_label: formatChatTime(new Date().toISOString()),
        });
      }
      renderChatMessages();
      setChatStatus(payload.source === "gemini" || payload.source === "cache" ? "AI javobi tayyor" : "Dashboard javobi tayyor", payload.source === "fallback" ? "cy" : "cg");
    } catch (error) {
      console.error(error);
      state.chat.messages = state.chat.messages.filter((item) => item.id !== localLoadingId);
      state.chat.messages.push({
        id: `assistant-error-${Date.now()}`,
        role: "assistant",
        content: "Javobni olishda xatolik bo'ldi. Iltimos qayta urinib ko'ring.",
        source: "fallback",
        created_at: new Date().toISOString(),
        created_label: formatChatTime(new Date().toISOString()),
      });
      renderChatMessages();
      setChatStatus("Chat vaqtincha band", "cy");
    } finally {
      state.chat.loading = false;
    }
  }

  function openAiAnswerModal(question, answer, source) {
    const modal = el("ai-answer-modal");
    if (!modal) return;
    modal.classList.add("open");
    document.body.style.overflow = "hidden";
    if (el("ai-answer-question")) el("ai-answer-question").textContent = question || "AI savoli";
    if (el("ai-answer-body")) el("ai-answer-body").textContent = answer || "Javob topilmadi.";
    setChipState("ai-answer-source", source || "AI", source === "fallback" ? "cy" : "cc");
  }

  function closeAiAnswerModal() {
    const modal = el("ai-answer-modal");
    if (!modal) return;
    modal.classList.remove("open");
    document.body.style.overflow = "";
  }

  async function askDirectorQuestion(rawQuestion) {
    const question = String(rawQuestion || "").trim();
    if (!AI_ASK_URL || !question) return;

    setChipState("aiAskStatus", "AI o'ylayapti...", "cc");
    openAiAnswerModal(question, "Savol tahlil qilinmoqda...", "AI");

    try {
      const response = await fetch(buildUrl(AI_ASK_URL), {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ question }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      openAiAnswerModal(payload.question || question, payload.answer || "Javob topilmadi.", payload.source === "fallback" ? "Fallback" : "Gemini");
      setChipState("aiAskStatus", "Javob tayyor", "cg");
    } catch (error) {
      console.error(error);
      openAiAnswerModal(question, "AI javobini olishda xatolik bo'ldi. Iltimos birozdan keyin qayta urinib ko'ring.", "Fallback");
      setChipState("aiAskStatus", "AI vaqtincha band", "cy");
    }
  }

  function askPresetQuestion(question) {
    if (el("aiQuestionInput")) el("aiQuestionInput").value = question;
    askDirectorQuestion(question);
  }

  function renderTeacherTable(targetId, rows, detailed) {
    const table = el(targetId);
    if (!table) return;
    if (!rows.length) {
      table.innerHTML = '<tbody><tr><td>Ustoz ma\'lumoti topilmadi.</td></tr></tbody>';
      return;
    }
    table.innerHTML = detailed ? `
      <thead>
        <tr>
          <th>#</th>
          <th style="text-align:left;">Ustoz</th>
          <th style="text-align:right;">Daromad</th>
          <th style="text-align:right;">Oldingi oy</th>
          <th style="text-align:right;">Sof foyda</th>
          <th style="text-align:center;">Guruh</th>
          <th style="text-align:center;">O'quvchi</th>
          <th style="text-align:center;">Davomat</th>
          <th style="text-align:center;">Retention</th>
          <th style="text-align:center;">Trend</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((row, index) => `
          <tr>
            <td>${index + 1}</td>
            <td>
              <div style="display:flex;align-items:center;gap:8px;">
                <div style="width:28px;height:28px;border-radius:50%;background:${index % 2 === 0 ? COLORS.cyan : COLORS.amber};color:#071018;display:flex;align-items:center;justify-content:center;font-size:.59rem;font-weight:800;flex-shrink:0;">${escapeHtml(initials(row.teacher_name))}</div>
                <span style="font-weight:600;color:#e2e8f0;white-space:nowrap;">${escapeHtml(row.teacher_name)}</span>
              </div>
            </td>
            <td style="text-align:right;font-weight:700;color:#f1f5f9;">${compactMoney(row.revenue || 0)}</td>
            <td style="text-align:right;color:rgba(255,255,255,.58);white-space:nowrap;">${compactMoney(row.revenue_previous || 0)}</td>
            <td style="text-align:right;font-weight:700;color:${COLORS.emerald};">${compactMoney(row.soft_profit || 0)}</td>
            <td style="text-align:center;color:${COLORS.violet};font-weight:700;">${formatInteger(row.groups || 0)}</td>
            <td style="text-align:center;color:${COLORS.cyan};font-weight:700;">${formatInteger(row.students || 0)}</td>
            <td style="text-align:center;color:${COLORS.white};">${displayPct(row.attendance_rate)}</td>
            <td style="text-align:center;color:${COLORS.amber};">${displayPct(row.retention_rate)}</td>
            <td style="text-align:center;">
              <div style="display:flex;flex-direction:column;align-items:center;gap:3px;">
                <span class="chip ${toneClassByValue(row.revenue_growth)}">${signedPct(row.revenue_growth || 0)}</span>
                <span style="font-size:.58rem;color:rgba(255,255,255,.24);line-height:1;">o‘tgan oy</span>
              </div>
            </td>
          </tr>
        `).join("")}
      </tbody>
    ` : `
      <thead>
        <tr>
          <th>#</th>
          <th style="text-align:left;">Ustoz</th>
          <th style="text-align:center;">Guruh</th>
          <th style="text-align:center;">O'quvchi</th>
          <th style="text-align:right;">Daromad</th>
          <th style="text-align:right;">Oldingi oy</th>
          <th style="text-align:center;">Trend</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((row, index) => `
          <tr>
            <td>${index === 0 ? "#1" : index + 1}</td>
            <td>
              <div style="display:flex;align-items:center;gap:8px;">
                <div style="width:28px;height:28px;border-radius:50%;background:${index % 2 === 0 ? COLORS.cyan : COLORS.amber};color:#071018;display:flex;align-items:center;justify-content:center;font-size:.59rem;font-weight:800;flex-shrink:0;">${escapeHtml(initials(row.teacher_name))}</div>
                <span style="font-weight:600;color:#e2e8f0;white-space:nowrap;">${escapeHtml(row.teacher_name)}</span>
              </div>
            </td>
            <td style="text-align:center;color:${COLORS.violet};font-weight:700;">${formatInteger(row.groups || 0)}</td>
            <td style="text-align:center;color:${COLORS.cyan};font-weight:700;">${formatInteger(row.students || 0)}</td>
            <td style="text-align:right;font-weight:700;color:#f1f5f9;white-space:nowrap;">${compactMoney(row.revenue || 0)}</td>
            <td style="text-align:right;color:rgba(255,255,255,.52);white-space:nowrap;">${compactMoney(row.revenue_previous || 0)}</td>
            <td style="text-align:center;">
              <div style="display:flex;flex-direction:column;align-items:center;gap:3px;">
                <span class="chip ${toneClassByValue(row.revenue_growth)}">${signedPct(row.revenue_growth || 0)}</span>
                <span style="font-size:.58rem;color:rgba(255,255,255,.24);line-height:1;">o‘tgan oy</span>
              </div>
            </td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderTeachers() {
    const teachers = state.data?.teachers || {};
    const ranking = teachers.ranking || [];
    if (el("teacher-count")) el("teacher-count").textContent = `${formatInteger(teachers.total_count || ranking.length)} ustoz`;
    renderTeacherTable("teacher-tbl", ranking.slice(0, 5), false);

    const summary = el("teacher-summary-grid");
    if (summary) {
      const avgRetention = ranking.length ? ranking.reduce((sum, item) => sum + Number(item.retention_rate || 0), 0) / ranking.length : 0;
      summary.innerHTML = [
        metricTile("Jami ustoz", formatInteger(teachers.total_count || ranking.length), "Aktiv o'qituvchilar"),
        metricTile("Trend", signedPct(ranking[0]?.revenue_growth || 0), "Yetakchi ustoz bo'yicha"),
        metricTile("Retention", displayPct(avgRetention), "O'quvchini ushlab qolish"),
        metricTile("Kuzatuvdagi", formatInteger((teachers.at_risk || []).length), "Aralashuv kerak"),
      ].join("");
    }

    const alerts = el("teacher-alert-list");
    if (alerts) {
      alerts.innerHTML = (teachers.at_risk || []).length
        ? teachers.at_risk.slice(0, 5).map((item) => stackRow(
            item.teacher_name,
            `Davomat ${displayPct(item.attendance_rate)} - Qarz ulushi ${displayPct(item.debt_ratio)}`,
            `${formatInteger(item.health_score)} ball`,
            COLORS.rose
          )).join("")
        : '<div class="loading-shell">Kuzatuvdagi ustoz topilmadi.</div>';
    }

    if (el("teacher-deep-count")) {
      el("teacher-deep-count").textContent = `${formatInteger(teachers.total_count || ranking.length)} ustoz`;
    }
    renderTeacherTable("teacher-deep-tbl", ranking, true);
  }

  function renderGroups() {
    const groups = state.data?.groups?.profitability || [];
    const topRows = [...groups].sort((a, b) => Number(b.revenue || 0) - Number(a.revenue || 0)).slice(0, 8);
    if (el("grp-count")) el("grp-count").textContent = `${formatInteger(groups.length)} guruh`;
    const table = el("groups-tbl");
    if (!table) return;
    if (!topRows.length) {
      table.innerHTML = '<tbody><tr><td>Guruh ma\'lumoti topilmadi.</td></tr></tbody>';
      return;
    }
    table.innerHTML = `
      <thead>
        <tr>
          <th style="text-align:left;">Guruh nomi</th>
          <th style="text-align:left;">Ustoz</th>
          <th style="text-align:center;">Bo'lim</th>
          <th style="text-align:center;">O'quvchi</th>
          <th style="text-align:right;">Daromad</th>
          <th style="text-align:center;">Bandlik</th>
          <th style="text-align:center;">Holat</th>
        </tr>
      </thead>
      <tbody>
        ${topRows.map((row) => `
          <tr>
            <td><span style="font-weight:600;color:${COLORS.white};">${escapeHtml(row.group_name)}</span></td>
            <td><span style="color:rgba(255,255,255,.48);">${escapeHtml(row.teacher_name || "Biriktirilmagan")}</span></td>
            <td style="text-align:center;"><span class="chip cp">${escapeHtml(row.category_name || "Noma'lum")}</span></td>
            <td style="text-align:center;color:${COLORS.cyan};font-weight:700;">${formatInteger(row.active_students || 0)}</td>
            <td style="text-align:right;font-weight:700;color:${COLORS.white};">${compactMoney(row.revenue || 0)}</td>
            <td style="text-align:center;color:${COLORS.amber};font-weight:700;">${displayPct(row.fill_rate)}</td>
            <td style="text-align:center;"><span class="chip ${healthChip(row)}">${escapeHtml(row.health_label || "Noma'lum")}</span></td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderStudents() {
    const students = state.data?.students || {};
    const total = students.total || 0;
    const active = students.active_students || 0;
    const inactive = students.inactive_students || 0;
    const dropped = students.dropouts || 0;
    const debtors = students.debtors_count || 0;
    const riskRows = students.risk_students || [];

    const summary = el("student-summary-grid");
    if (summary) {
      summary.innerHTML = [
        metricTile("Jami o'quvchi", formatInteger(total), "Tanlangan filtr doirasida"),
        metricTile("Faol o'quvchi", formatInteger(active), `${signedPct(students.growth_pct || 0)} o'sish`),
        metricTile("Yangi qo'shilgan", formatInteger(students.new_count || 0), "Tanlangan davr ichida"),
        metricTile("Qarzdor", formatInteger(debtors), compactMoney(students.debt_amount || 0)),
      ].join("");
    }

    if (el("student-debt-chip")) el("student-debt-chip").textContent = `${formatInteger(debtors)} qarzdor`;
    if (el("student-status-total")) el("student-status-total").textContent = formatInteger(total);

    const chart = ensureChart("students", "student-status-chart", () => ({
      type: "doughnut",
      data: { labels: [], datasets: [{ data: [], backgroundColor: [] }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "70%", plugins: { legend: { display: false } } },
    }));
    if (chart) {
      chart.data.labels = ["Aktiv", "Noaktiv", "Tark etgan"];
      chart.data.datasets[0].data = [active, inactive, dropped];
      chart.data.datasets[0].backgroundColor = [COLORS.emerald, COLORS.amber, COLORS.rose];
      chart.update();
    }

    if (el("student-status-legend")) {
      el("student-status-legend").innerHTML = [
        stackRow("Aktiv", "Darsda qatnashayotganlar", formatInteger(active), COLORS.emerald),
        stackRow("Noaktiv", "Hozir aktiv guruhsizlar", formatInteger(inactive), COLORS.amber),
        stackRow("Tark etgan", "Arxiv yoki chiqib ketganlar", formatInteger(dropped), COLORS.rose),
        stackRow("Riskda", "Aralashuv kerak", formatInteger(riskRows.length), COLORS.violet),
      ].join("");
    }

    if (el("student-risk-count")) el("student-risk-count").textContent = `${formatInteger(riskRows.length)} ta`;

    const table = el("student-risk-tbl");
    if (table) {
      table.innerHTML = !riskRows.length ? '<tbody><tr><td>Xavfdagi o\'quvchilar topilmadi.</td></tr></tbody>' : `
        <thead>
          <tr>
            <th style="text-align:left;">O'quvchi</th>
            <th style="text-align:left;">Guruh</th>
            <th style="text-align:center;">Davomat</th>
            <th style="text-align:right;">Qarz</th>
            <th style="text-align:center;">Risk</th>
            <th style="text-align:left;">Sabab</th>
          </tr>
        </thead>
        <tbody>
          ${riskRows.slice(0, 12).map((row) => `
            <tr>
              <td><span style="font-weight:700;color:${COLORS.white};">${escapeHtml(row.name)}</span></td>
              <td><span style="color:rgba(255,255,255,.48);">${escapeHtml(row.course || "Guruhsiz")}</span></td>
              <td style="text-align:center;color:${COLORS.cyan};font-weight:700;">${escapeHtml(row.attendance_pct || "-")}</td>
              <td style="text-align:right;color:${COLORS.amber};font-weight:700;">${compactMoney(row.debt || 0)}</td>
              <td style="text-align:center;"><span class="chip ${Number(row.risk_score || 0) >= 70 ? "cr" : "cy"}">${formatInteger(row.risk_score || 0)}</span></td>
              <td style="color:rgba(255,255,255,.52);">${escapeHtml(row.reason || "-")}</td>
            </tr>
          `).join("")}
        </tbody>
      `;
    }
  }

  function renderLeads() {
    const marketing = state.data?.marketing || {};
    const sources = marketing.sources || [];
    const funnel = marketing.funnel || [];
    const chart = ensureChart("leadOrbit", "lead-orbit-chart", () => ({
      type: "doughnut",
      data: { labels: [], datasets: [{ data: [], backgroundColor: [] }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "70%", plugins: { legend: { display: false } } },
    }));
    if (chart) {
      chart.data.labels = ["Bu davr", "Avvalgi baza", "To'lovga aylangan"];
      chart.data.datasets[0].data = [
        marketing.total_leads || 0,
        Math.max((marketing.all_time_leads || 0) - (marketing.total_leads || 0), 0),
        marketing.paid_students || 0,
      ];
      chart.data.datasets[0].backgroundColor = [COLORS.amber, COLORS.cyan, COLORS.emerald];
      chart.update();
    }

    if (el("lead-total-chip")) el("lead-total-chip").textContent = `${formatInteger(marketing.all_time_leads || 0)} jami`;
    if (el("lead-orbit-total")) el("lead-orbit-total").textContent = formatInteger(marketing.total_leads || 0);
    if (el("lead-orbit-meta")) {
      el("lead-orbit-meta").innerHTML = [
        stackRow("Umumiy lead", "Markaz bo'yicha barcha leadlar", formatInteger(marketing.all_time_leads || 0), COLORS.cyan),
        stackRow("O'tgan davr", "Taqqoslash uchun", formatInteger(marketing.total_leads_previous || 0), COLORS.slate),
        stackRow("To'lov qilgan", "Leadlardan to'lovga o'tganlar", formatInteger(marketing.paid_students || 0), COLORS.emerald),
        stackRow("Faol o'quvchi", "Leaddan aktiv statusgacha", formatInteger(marketing.active_students || 0), COLORS.amber),
      ].join("");
    }

    const summary = el("lead-summary-grid");
    if (summary) {
      summary.innerHTML = [
        metricTile("Joriy lead", formatInteger(marketing.total_leads || 0), `${signedPct(marketing.conversion_growth || 0)} o'zgarish`),
        metricTile("Bog'lanish", displayPct(marketing.contact_rate || 0), "Leadga qayta aloqa ulushi"),
        metricTile("Konversiya", displayPct(marketing.conversion_rate || 0), "To'lovga aylanganlar"),
        metricTile("Faolga aylanish", displayPct(marketing.active_conversion_rate || 0), "Aktiv studentgacha"),
      ].join("");
    }

    const bestNote = el("lead-best-note");
    if (bestNote) {
      bestNote.textContent = marketing.best_source
        ? `${marketing.best_source.name} eng kuchli manba bo'lib turibdi: ${formatInteger(marketing.best_source.count)} lead va ${displayPct(marketing.best_source.conversion)} konversiya.`
        : "Lead manbalari bo'yicha yetarli ma'lumot topilmadi.";
    }

    renderFunnelInto("lead-funnel-wrap", funnel);

    if (el("lead-source-count")) el("lead-source-count").textContent = `${formatInteger(sources.length)} manba`;
    const table = el("lead-source-tbl");
    if (table) {
      table.innerHTML = !sources.length ? '<tbody><tr><td>Lead manbalari topilmadi.</td></tr></tbody>' : `
        <thead>
          <tr>
            <th style="text-align:left;">Manba</th>
            <th style="text-align:center;">Lead</th>
            <th style="text-align:center;">Sinov</th>
            <th style="text-align:center;">Konversiya</th>
            <th style="text-align:center;">Faol</th>
            <th style="text-align:right;">Daromad</th>
          </tr>
        </thead>
        <tbody>
          ${sources.map((row) => `
            <tr>
              <td><span style="font-weight:700;color:${COLORS.white};">${escapeHtml(row.name)}</span></td>
              <td style="text-align:center;color:${COLORS.cyan};font-weight:700;">${formatInteger(row.count || 0)}</td>
              <td style="text-align:center;color:${COLORS.amber};font-weight:700;">${formatInteger(row.trial_attended || row.trial_scheduled || 0)}</td>
              <td style="text-align:center;"><span class="chip ${Number(row.conversion || 0) >= 25 ? "cg" : Number(row.conversion || 0) >= 12 ? "cy" : "cr"}">${displayPct(row.conversion || 0)}</span></td>
              <td style="text-align:center;color:${COLORS.emerald};font-weight:700;">${formatInteger(row.active_students || 0)}</td>
              <td style="text-align:right;color:${COLORS.white};font-weight:700;">${compactMoney(row.revenue || 0)}</td>
            </tr>
          `).join("")}
        </tbody>
      `;
    }
  }

  function renderRequests() {
    const requests = state.data?.requests || {};
    const items = requests.items || [];
    const summary = el("request-summary-grid");
    if (summary) {
      summary.innerHTML = [
        metricTile("Jami so'rov", formatInteger(requests.total_count || 0), `${signedPct(requests.growth || 0)} o'zgarish`),
        metricTile("Kutilmoqda", formatInteger(requests.pending_count || 0), "Ko'rib chiqilishi kerak"),
        metricTile("Tasdiqlangan", formatInteger(requests.approved_count || 0), "Managerlar ko'rib chiqqan"),
        metricTile("Qiymat", compactMoney(requests.total_value_som || 0), `${formatInteger(requests.total_value_chaqmoq || 0)} chaqmoq`),
      ].join("");
    }

    if (el("request-growth-chip")) {
      el("request-growth-chip").className = `chip ${toneClassByValue(requests.growth)}`;
      el("request-growth-chip").textContent = signedPct(requests.growth || 0);
    }
    if (el("request-status-total")) el("request-status-total").textContent = formatInteger(requests.total_count || 0);
    if (el("request-count-chip")) el("request-count-chip").textContent = `${formatInteger(requests.total_count || 0)} so'rov`;

    const chart = ensureChart("requests", "request-status-chart", () => ({
      type: "doughnut",
      data: { labels: [], datasets: [{ data: [], backgroundColor: [] }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "70%", plugins: { legend: { display: false } } },
    }));
    if (chart) {
      chart.data.labels = ["Kutilmoqda", "Tasdiqlandi", "Rad etildi"];
      chart.data.datasets[0].data = [requests.pending_count || 0, requests.approved_count || 0, requests.rejected_count || 0];
      chart.data.datasets[0].backgroundColor = [COLORS.amber, COLORS.emerald, COLORS.rose];
      chart.update();
    }

    if (el("request-status-legend")) {
      el("request-status-legend").innerHTML = [
        stackRow("Kutilmoqda", "Do'kon manageri ko'rishi kerak", formatInteger(requests.pending_count || 0), COLORS.amber),
        stackRow("Tasdiqlandi", "Qabul qilingan so'rovlar", formatInteger(requests.approved_count || 0), COLORS.emerald),
        stackRow("Rad etildi", "Bekor qilinganlar", formatInteger(requests.rejected_count || 0), COLORS.rose),
        stackRow("Mahsulot soni", "Jami talab qilingan dona", formatInteger(requests.total_qty || 0), COLORS.cyan),
      ].join("");
    }

    const topProducts = el("request-top-products");
    if (topProducts) {
      topProducts.innerHTML = (requests.top_products || []).length
        ? requests.top_products.map((row) => stackRow(row.name, `${formatInteger(row.count)} ta so'rov`, `${formatInteger(row.qty)} dona`, COLORS.cyan)).join("")
        : '<div class="loading-shell">Mahsulotlar bo\'yicha ma\'lumot topilmadi.</div>';
    }

    const table = el("requests-tbl");
    if (table) {
      table.innerHTML = !items.length ? '<tbody><tr><td>So\'rovlar topilmadi.</td></tr></tbody>' : `
        <thead>
          <tr>
            <th style="text-align:left;">O'quvchi</th>
            <th style="text-align:left;">Mahsulot</th>
            <th style="text-align:center;">Soni</th>
            <th style="text-align:center;">Holat</th>
            <th style="text-align:left;">Manager</th>
            <th style="text-align:right;">Qiymat</th>
            <th style="text-align:right;">Sana</th>
          </tr>
        </thead>
        <tbody>
          ${items.map((row) => `
            <tr>
              <td><span style="font-weight:700;color:${COLORS.white};">${escapeHtml(row.student_name)}</span></td>
              <td><span style="color:rgba(255,255,255,.58);">${escapeHtml(row.product_name)}</span></td>
              <td style="text-align:center;color:${COLORS.cyan};font-weight:700;">${formatInteger(row.qty || 0)}</td>
              <td style="text-align:center;"><span class="chip ${row.status === "approved" ? "cg" : row.status === "rejected" ? "cr" : "cy"}">${escapeHtml(row.status_label)}</span></td>
              <td style="color:rgba(255,255,255,.58);">${escapeHtml(row.manager_name)}</td>
              <td style="text-align:right;color:${COLORS.amber};font-weight:700;">${compactMoney(row.value_som || 0)}</td>
              <td style="text-align:right;color:rgba(255,255,255,.42);">${escapeHtml(row.created_at)}</td>
            </tr>
          `).join("")}
        </tbody>
      `;
    }
  }

  function openModal(item) {
    const modal = el("kpi-modal");
    if (!modal || !item) return;
    modal.classList.add("open");
    document.body.style.overflow = "hidden";
    state.modalDetailTarget = getModalDetailTarget(item);

    if (el("modal-title")) el("modal-title").textContent = item.label;
    if (el("modal-val")) el("modal-val").textContent = item.value;
    if (el("modal-accent")) el("modal-accent").style.background = `linear-gradient(90deg,transparent,${item.color},transparent)`;
    if (el("modal-ico")) {
      el("modal-ico").style.background = `${item.color}1a`;
      el("modal-ico").style.border = `1px solid ${item.color}28`;
      el("modal-ico").style.color = item.color;
      el("modal-ico").innerHTML = iconSvg(item.key);
    }
    if (el("modal-delta")) {
      el("modal-delta").className = `chip ${item.deltaText ? "cn" : toneClassByValue(item.delta)}`;
      el("modal-delta").textContent = item.deltaText || `${signedPct(item.delta)} oldingi davrga nisbatan`;
    }
    if (el("modal-detail-btn")) {
      if (state.modalDetailTarget) {
        el("modal-detail-btn").style.display = "inline-flex";
        el("modal-detail-btn").style.background = `${item.color}12`;
        el("modal-detail-btn").style.borderColor = `${item.color}28`;
        el("modal-detail-btn").style.color = item.color;
        el("modal-detail-btn").textContent = state.modalDetailTarget.buttonText || "Batafsil";
        el("modal-detail-btn").title = state.modalDetailTarget.title || "Batafsil";
      } else {
        el("modal-detail-btn").style.display = "none";
      }
    }

    const values = item.spark || [];
    const avg = values.length ? values.reduce((sum, value) => sum + Number(value || 0), 0) / values.length : 0;
    const max = values.length ? Math.max(...values) : 0;
    const min = values.length ? Math.min(...values) : 0;
    if (el("m-avg")) {
      el("m-avg").textContent = compactNumber(avg);
      el("m-avg").style.color = item.color;
    }
    if (el("m-max")) el("m-max").textContent = compactNumber(max);
    if (el("m-min")) el("m-min").textContent = compactNumber(min);

    if (state.modalChart) state.modalChart.destroy();
    const canvas = el("modal-chart");
    if (canvas && window.Chart) {
      state.modalChart = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
          labels: item.labels || [],
          datasets: [{
            data: values,
            borderColor: item.color,
            borderWidth: 2.5,
            fill: true,
            pointRadius: 4,
            pointHoverRadius: 6,
            pointBackgroundColor: item.color,
            tension: 0.42,
            backgroundColor(context) {
              const gradient = context.chart.ctx.createLinearGradient(0, 0, 0, context.chart.height);
              gradient.addColorStop(0, `${item.color}3e`);
              gradient.addColorStop(1, `${item.color}00`);
              return gradient;
            },
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title(items) {
                  const label = items?.[0]?.label;
                  return formatApiDate(label, { includeYear: true });
                },
              },
            },
          },
          scales: {
            x: {
              grid: { color: "rgba(255,255,255,.04)" },
              ticks: {
                color: "rgba(255,255,255,.3)",
                autoSkip: false,
                maxRotation: 0,
                minRotation: 0,
                callback(value) {
                  return formatApiDate(this.getLabelForValue(value), { includeYear: false, multiline: true });
                },
              },
            },
            y: { grid: { color: "rgba(255,255,255,.04)" }, ticks: { color: "rgba(255,255,255,.25)" } },
          },
        },
      });
    }
  }

  function closeModal() {
    const modal = el("kpi-modal");
    if (modal) modal.classList.remove("open");
    document.body.style.overflow = "";
    state.modalDetailTarget = null;
    if (el("modal-detail-btn")) {
      el("modal-detail-btn").style.display = "none";
      el("modal-detail-btn").textContent = "Batafsil";
      el("modal-detail-btn").title = "Batafsil";
    }
    if (state.modalChart) {
      state.modalChart.destroy();
      state.modalChart = null;
    }
  }

  function formatDateTimeForExport(value = new Date()) {
    return new Intl.DateTimeFormat("uz-UZ", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(value);
  }

  function getExportRangeLabel() {
    const system = state.data?.system || {};
    return formatDateRange(system.start_date, system.end_date);
  }

  function getExportMeta() {
    return {
      centerName: document.querySelector(".center-name")?.textContent?.trim() || "Chaqmoq",
      directorName: document.querySelector(".profile-name")?.textContent?.trim() || "Direktor",
      exportedAt: formatDateTimeForExport(),
      rangeLabel: getExportRangeLabel(),
    };
  }

  function csvEscape(value) {
    return `"${String(value ?? "").replace(/"/g, '""')}"`;
  }

  function formatMoneyFull(value) {
    return `${formatInteger(value || 0)} UZS`;
  }

  function buildCsvRows() {
    const data = state.data || {};
    const finance = data.finance || {};
    const managers = data.managers || {};
    const teachers = data.teachers || {};
    const students = data.students || {};
    const requests = data.requests || {};
    const groups = data.groups || {};
    const meta = getExportMeta();

    const sections = [
      {
        title: "Dashboard xulosasi",
        rows: [
          { Maydon: "Markaz", Qiymat: meta.centerName },
          { Maydon: "Direktor", Qiymat: meta.directorName },
          { Maydon: "Davr", Qiymat: meta.rangeLabel },
          { Maydon: "Eksport vaqti", Qiymat: meta.exportedAt },
          { Maydon: "Managerlar", Qiymat: formatInteger(managers.total_count || 0) },
          { Maydon: "O'qituvchilar", Qiymat: formatInteger(teachers.total_count || 0) },
          { Maydon: "O'quvchilar", Qiymat: formatInteger(students.total || 0) },
          { Maydon: "Mahsulotlar", Qiymat: formatInteger(requests.products_count || 0) },
          { Maydon: "So'rovlar", Qiymat: formatInteger(requests.all_requests_count || 0) },
        ],
      },
      {
        title: "Asosiy KPI",
        rows: buildKpis().map((item) => ({
          Korsatkich: item.label,
          Qiymat: item.value,
          Ozgarish: signedPct(item.delta || 0),
          Izoh: item.sub,
        })),
      },
      {
        title: "To'lov holati",
        rows: [
          { Maydon: "Jami to'lov hajmi", Qiymat: formatMoneyFull(finance.income || 0) },
          { Maydon: "O'rtacha to'lov", Qiymat: formatMoneyFull(finance.avg_payment || 0) },
          { Maydon: "To'lov bajarilishi", Qiymat: `${formatInteger(finance.paid_students_count || 0)}/${formatInteger(finance.billed_students_count || 0)}` },
          { Maydon: "Daromad sifati", Qiymat: displayPct(finance.income_quality_score || 0) },
          { Maydon: "Qayta to'lov", Qiymat: displayPct(finance.recurring_share || 0) },
        ],
      },
      {
        title: "Ustozlar reytingi",
        rows: (teachers.ranking || []).map((row) => ({
          Ustoz: row.teacher_name,
          Daromad: formatMoneyFull(row.revenue || 0),
          OldingiOy: formatMoneyFull(row.revenue_previous || 0),
          Guruhlar: formatInteger(row.groups || 0),
          Oquvchilar: formatInteger(row.students || 0),
          Trend: signedPct(row.revenue_growth || 0),
        })),
      },
      {
        title: "Guruhlar",
        rows: (groups.profitability || []).map((row) => ({
          Guruh: row.group_name,
          Ustoz: row.teacher_name || "Biriktirilmagan",
          Bolim: row.category_name || "Noma'lum",
          Oquvchilar: formatInteger(row.active_students || 0),
          Daromad: formatMoneyFull(row.revenue || 0),
          Bandlik: displayPct(row.fill_rate || 0),
          Holat: row.health_label || "Noma'lum",
        })),
      },
      {
        title: "So'rovlar",
        rows: (requests.items || []).map((row) => ({
          Oquvchi: row.student_name,
          Mahsulot: row.product_name,
          Soni: formatInteger(row.qty || 0),
          Holat: row.status_label,
          Manager: row.manager_name,
          Qiymat: formatMoneyFull(row.value_som || 0),
          Sana: row.created_at,
        })),
      },
    ];

    return sections;
  }

  function downloadCsv(sections) {
    const usefulSections = (sections || []).filter((section) => Array.isArray(section.rows) && section.rows.length);
    if (!usefulSections.length) {
      window.alert("Eksport uchun ma'lumot topilmadi.");
      return;
    }

    const csvBlocks = usefulSections.map((section) => {
      const headers = Object.keys(section.rows[0]);
      const lines = [
        csvEscape(section.title),
        headers.map(csvEscape).join(";"),
        ...section.rows.map((row) => headers.map((header) => csvEscape(row[header])).join(";")),
      ];
      return lines.join("\n");
    });

    const csv = `\uFEFF${csvBlocks.join("\n\n")}`;
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `director-dashboard-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function metricCardHtml(label, value, note) {
    return `
      <div class="metric-card">
        <div class="metric-label">${escapeHtml(label)}</div>
        <div class="metric-value">${escapeHtml(value)}</div>
        ${note ? `<div class="metric-note">${escapeHtml(note)}</div>` : ""}
      </div>
    `;
  }

  function reportTableHtml(columns, rows, emptyText = "Ma'lumot topilmadi.") {
    if (!rows.length) {
      return `<div class="empty-note">${escapeHtml(emptyText)}</div>`;
    }
    return `
      <table class="report-table">
        <thead>
          <tr>
            ${columns.map((col) => `<th style="${col.align ? `text-align:${col.align};` : ""}">${escapeHtml(col.label)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              ${columns.map((col) => `<td style="${col.align ? `text-align:${col.align};` : ""}">${escapeHtml(col.render ? col.render(row) : row[col.key])}</td>`).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  function buildPrintDocumentHtml() {
    const data = state.data || {};
    const finance = data.finance || {};
    const teachers = data.teachers || {};
    const groups = data.groups || {};
    const requests = data.requests || {};
    const meta = getExportMeta();
    const revenueChart = el("rev-chart")?.toDataURL("image/png", 1.0) || "";
    const donutChart = el("donut-chart")?.toDataURL("image/png", 1.0) || "";
    const overviewCards = [
      ["Managerlar", `${formatInteger(data.managers?.total_count || 0)} ta`, "Aktiv boshqaruv xodimlari"],
      ["O'qituvchilar", `${formatInteger(teachers.total_count || 0)} ta`, "Dars olib borayotgan ustozlar"],
      ["O'quvchilar", `${formatInteger(data.students?.total || 0)} ta`, "Baza bo'yicha jami o'quvchi"],
      ["Mahsulotlar", `${formatInteger(requests.products_count || 0)} ta`, "Do'kondagi mahsulotlar"],
      ["So'rovlar", `${formatInteger(requests.all_requests_count || 0)} ta`, "Yuborilgan barcha so'rovlar"],
    ];
    const kpiCards = buildKpis();
    const paymentRows = [
      ["Jami to'lov hajmi", formatMoneyFull(finance.income || 0)],
      ["O'rtacha to'lov", formatMoneyFull(finance.avg_payment || 0)],
      ["To'lov bajarildi", `${formatInteger(finance.paid_students_count || 0)}/${formatInteger(finance.billed_students_count || 0)}`],
      ["Daromad sifati", displayPct(finance.income_quality_score || 0)],
      ["Qayta to'lov", displayPct(finance.recurring_share || 0)],
    ];

    return `<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <title>ChaqmoqApp Direktor Report ${escapeHtml(meta.rangeLabel)}</title>
  <style>
    @page { size: A4 portrait; margin: 12mm; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      color: #0f172a;
      background: #f8fafc;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .report-shell { display: flex; flex-direction: column; gap: 18px; }
    .report-header {
      border: 1px solid #dbe3ef;
      border-radius: 18px;
      padding: 18px 20px;
      background: linear-gradient(180deg, #ffffff, #f8fbff);
    }
    .report-brand {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .brand-left { display: flex; align-items: center; gap: 14px; }
    .brand-badge {
      width: 46px; height: 46px; border-radius: 14px;
      background: linear-gradient(135deg, #f59e0b, #d97706);
      color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-size: 22px; font-weight: 900;
      box-shadow: 0 10px 24px rgba(245,158,11,.18);
    }
    .report-title { font-size: 22px; font-weight: 900; letter-spacing: -.03em; margin: 0; }
    .report-subtitle { margin: 4px 0 0; color: #475569; font-size: 13px; }
    .report-meta {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 16px;
    }
    .meta-card, .metric-card, .summary-card, .chart-card, .table-card {
      border: 1px solid #dbe3ef;
      border-radius: 16px;
      background: #fff;
    }
    .meta-card { padding: 12px 14px; }
    .meta-label, .metric-label, .section-kicker {
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .12em;
      color: #64748b;
    }
    .meta-value { margin-top: 6px; font-size: 14px; font-weight: 700; color: #0f172a; }
    .summary-grid, .kpi-grid {
      display: grid;
      gap: 10px;
    }
    .summary-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .kpi-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .summary-card {
      padding: 14px;
      border-top: 3px solid #f59e0b;
      background: linear-gradient(180deg, #ffffff, #f9fafb);
    }
    .summary-value { margin-top: 8px; font-size: 20px; font-weight: 900; color: #0f172a; }
    .summary-note, .metric-note { margin-top: 5px; color: #64748b; font-size: 12px; line-height: 1.45; }
    .metric-card {
      padding: 14px;
      border-top: 3px solid #3b82f6;
      min-height: 112px;
    }
    .metric-value { margin-top: 8px; font-size: 22px; font-weight: 900; color: #0f172a; line-height: 1.15; }
    .charts-grid {
      display: grid;
      grid-template-columns: 1.25fr .75fr;
      gap: 14px;
      break-inside: avoid;
    }
    .chart-card, .table-card { padding: 16px 18px; }
    .chart-card img {
      width: 100%;
      display: block;
      border-radius: 14px;
      border: 1px solid #e2e8f0;
      background: #fff;
    }
    .payment-list {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 14px;
    }
    .payment-item {
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 12px;
      background: #f8fafc;
    }
    .payment-item strong {
      display: block;
      margin-top: 5px;
      font-size: 15px;
      color: #0f172a;
    }
    .report-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
    }
    .report-table th {
      padding: 10px 10px;
      border-bottom: 1px solid #dbe3ef;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: #64748b;
    }
    .report-table td {
      padding: 10px 10px;
      border-bottom: 1px solid #edf2f7;
      font-size: 13px;
      color: #0f172a;
      vertical-align: top;
    }
    .report-table tbody tr:last-child td { border-bottom: none; }
    .section-title {
      margin: 4px 0 0;
      font-size: 19px;
      font-weight: 900;
      letter-spacing: -.02em;
      color: #0f172a;
    }
    .section-note {
      margin-top: 6px;
      color: #64748b;
      font-size: 12px;
      line-height: 1.5;
    }
    .table-card + .table-card { margin-top: 14px; }
    .page-break { break-before: page; }
    .empty-note {
      margin-top: 10px;
      padding: 14px;
      border: 1px dashed #cbd5e1;
      border-radius: 12px;
      color: #64748b;
      font-size: 13px;
      background: #f8fafc;
    }
    @media print {
      .page-break { break-before: page; }
    }
  </style>
</head>
<body>
  <div class="report-shell">
    <section class="report-header">
      <div class="report-brand">
        <div class="brand-left">
          <div class="brand-badge">⚡</div>
          <div>
            <h1 class="report-title">ChaqmoqApp Direktor Dashboard</h1>
            <div class="report-subtitle">${escapeHtml(meta.centerName)} markazi uchun eksport hisobot</div>
          </div>
        </div>
        <div style="text-align:right;">
          <div class="section-kicker">Eksport</div>
          <div class="meta-value">${escapeHtml(meta.exportedAt)}</div>
        </div>
      </div>
      <div class="report-meta">
        <div class="meta-card">
          <div class="meta-label">Davr</div>
          <div class="meta-value">${escapeHtml(meta.rangeLabel)}</div>
        </div>
        <div class="meta-card">
          <div class="meta-label">Direktor</div>
          <div class="meta-value">${escapeHtml(meta.directorName)}</div>
        </div>
        <div class="meta-card">
          <div class="meta-label">Holat</div>
          <div class="meta-value">Jonli snapshot</div>
        </div>
      </div>
    </section>

    <section class="summary-grid">
      ${overviewCards.map(([label, value, note]) => `
        <div class="summary-card">
          <div class="section-kicker">${escapeHtml(label)}</div>
          <div class="summary-value">${escapeHtml(value)}</div>
          <div class="summary-note">${escapeHtml(note)}</div>
        </div>
      `).join("")}
    </section>

    <section class="kpi-grid">
      ${kpiCards.map((item) => metricCardHtml(item.label, item.value, `${signedPct(item.delta || 0)} · ${item.sub}`)).join("")}
    </section>

    <section class="charts-grid">
      <div class="chart-card">
        <div class="section-kicker">Moliya</div>
        <div class="section-title">Daromad va xarajat</div>
        <div class="section-note">Joriy davr moliyaviy dinamikasi eksport uchun toza ko‘rinishda berildi.</div>
        ${revenueChart ? `<img src="${revenueChart}" alt="Daromad va xarajat chart">` : `<div class="empty-note">Chart tasviri topilmadi.</div>`}
      </div>
      <div class="chart-card">
        <div class="section-kicker">To'lovlar</div>
        <div class="section-title">To'lov holati</div>
        <div class="section-note">To‘lov bajarilishi va asosiy metrikalar.</div>
        ${donutChart ? `<img src="${donutChart}" alt="To'lov holati chart">` : `<div class="empty-note">Chart tasviri topilmadi.</div>`}
        <div class="payment-list">
          ${paymentRows.map(([label, value]) => `
            <div class="payment-item">
              <div class="meta-label">${escapeHtml(label)}</div>
              <strong>${escapeHtml(value)}</strong>
            </div>
          `).join("")}
        </div>
      </div>
    </section>

    <section class="table-card page-break">
      <div class="section-kicker">Ustozlar</div>
      <div class="section-title">Samaradorlik reytingi</div>
      <div class="section-note">Trend ustuni o‘tgan oyga nisbatan hisoblandi.</div>
      ${reportTableHtml(
        [
          { key: "teacher_name", label: "Ustoz" },
          { key: "groups", label: "Guruh", align: "center", render: (row) => formatInteger(row.groups || 0) },
          { key: "students", label: "O'quvchi", align: "center", render: (row) => formatInteger(row.students || 0) },
          { key: "revenue", label: "Daromad", align: "right", render: (row) => formatMoneyFull(row.revenue || 0) },
          { key: "revenue_previous", label: "Oldingi oy", align: "right", render: (row) => formatMoneyFull(row.revenue_previous || 0) },
          { key: "revenue_growth", label: "Trend", align: "center", render: (row) => signedPct(row.revenue_growth || 0) },
        ],
        (teachers.ranking || []).slice(0, 12),
        "Ustozlar reytingi uchun ma'lumot topilmadi."
      )}
    </section>

    <section class="table-card">
      <div class="section-kicker">Guruhlar</div>
      <div class="section-title">Barcha guruhlar</div>
      <div class="section-note">Daromad, bandlik va holat bo‘yicha eng muhim guruhlar ro‘yxati.</div>
      ${reportTableHtml(
        [
          { key: "group_name", label: "Guruh" },
          { key: "teacher_name", label: "Ustoz", render: (row) => row.teacher_name || "Biriktirilmagan" },
          { key: "category_name", label: "Bo'lim", render: (row) => row.category_name || "Noma'lum" },
          { key: "active_students", label: "O'quvchi", align: "center", render: (row) => formatInteger(row.active_students || 0) },
          { key: "revenue", label: "Daromad", align: "right", render: (row) => formatMoneyFull(row.revenue || 0) },
          { key: "fill_rate", label: "Bandlik", align: "center", render: (row) => displayPct(row.fill_rate || 0) },
          { key: "health_label", label: "Holat", align: "center", render: (row) => row.health_label || "Noma'lum" },
        ],
        (groups.profitability || []).slice(0, 14),
        "Guruhlar bo'yicha ma'lumot topilmadi."
      )}
    </section>

    <section class="table-card">
      <div class="section-kicker">So'rovlar</div>
      <div class="section-title">Do'kon so'rovlari</div>
      <div class="section-note">Oxirgi yuborilgan so‘rovlarning eksport ko‘rinishi.</div>
      ${reportTableHtml(
        [
          { key: "student_name", label: "O'quvchi" },
          { key: "product_name", label: "Mahsulot" },
          { key: "qty", label: "Soni", align: "center", render: (row) => formatInteger(row.qty || 0) },
          { key: "status_label", label: "Holat", align: "center" },
          { key: "manager_name", label: "Manager" },
          { key: "value_som", label: "Qiymat", align: "right", render: (row) => formatMoneyFull(row.value_som || 0) },
          { key: "created_at", label: "Sana", align: "right" },
        ],
        (requests.items || []).slice(0, 16),
        "So'rovlar topilmadi."
      )}
    </section>
  </div>
</body>
</html>`;
  }

  function openPdfReport() {
    if (!state.data) {
      window.alert("Eksport uchun ma'lumot hali yuklanmagan.");
      return;
    }
    const printWindow = window.open("", "_blank", "width=1280,height=900");
    if (!printWindow) {
      window.alert("PDF eksporti uchun yangi oynani ochib bo'lmadi. Brauzer popup'ni bloklagan bo'lishi mumkin.");
      return;
    }
    printWindow.document.open();
    printWindow.document.write(buildPrintDocumentHtml());
    printWindow.document.close();
    printWindow.focus();
    printWindow.onload = () => {
      setTimeout(() => {
        printWindow.print();
      }, 250);
    };
  }

  function toggleExport(event) {
    event.stopPropagation();
    const profileMenu = el("profile-dd");
    const profileTrigger = document.querySelector(".profile-trigger");
    if (profileMenu) profileMenu.classList.remove("show");
    if (profileTrigger) profileTrigger.setAttribute("aria-expanded", "false");
    const dropdown = el("exp-dd");
    if (!dropdown) return;
    dropdown.style.display = dropdown.style.display === "block" ? "none" : "block";
  }

  function toggleProfileMenu(event) {
    event.stopPropagation();
    const exportMenu = el("exp-dd");
    if (exportMenu) exportMenu.style.display = "none";
    const menu = el("profile-dd");
    const trigger = document.querySelector(".profile-trigger");
    if (!menu || !trigger) return;
    const isOpen = menu.classList.contains("show");
    menu.classList.toggle("show", !isOpen);
    trigger.setAttribute("aria-expanded", String(!isOpen));
  }

  function doExport(type) {
    const dropdown = el("exp-dd");
    if (dropdown) dropdown.style.display = "none";
    if (type === "PDF") {
      openPdfReport();
      return;
    }
    downloadCsv(buildCsvRows());
  }

  function bindTabs() {
    document.querySelectorAll("[data-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        const tab = button.dataset.tab;
        state.activeTab = tab;
        syncTabButtons();
        setTimeout(() => {
          Object.values(state.charts).forEach((chart) => {
            if (!chart) return;
            chart.resize?.();
            chart.update?.("none");
          });
        }, 60);
      });
    });
  }

  function bindFilters() {
    ["branchSelect", "teacherSelect", "categorySelect"].forEach((id) => {
      const select = el(id);
      if (!select) return;
      select.addEventListener("change", () => {
        if (state.hydrating) return;
        loadDashboard();
      });
    });
    ["dateFromInput", "dateToInput"].forEach((id) => {
      const input = el(id);
      if (!input) return;
      input.addEventListener("change", () => {
        if (state.hydrating) return;
        const dateFrom = String(el("dateFromInput")?.value || "").trim();
        const dateTo = String(el("dateToInput")?.value || "").trim();

        if (!dateFrom && !dateTo) {
          state.period = "bu_oy";
          setPeriodUi();
          loadDashboard();
          return;
        }

        if (dateFrom && dateTo) {
          if (dateFrom > dateTo) {
            const target = el("dateToInput");
            if (target) target.value = dateFrom;
          }
          state.period = "custom";
          setPeriodUi();
          loadDashboard();
        }
      });
    });
  }

  function bindAiChat() {
    const launcher = el("directorAiChatLauncher");
    const panel = el("directorAiChatPanel");
    const closeBtn = el("directorAiChatClose");
    const resetBtn = el("directorAiChatReset");
    const headerBtn = el("directorAiChatHeaderBtn");
    const header = el("directorAiChatHeader");
    const form = el("directorAiChatForm");
    const input = el("directorAiChatInput");
    if (!launcher || !panel) return;

    applyChatLauncherPosition(state.chat.position);
    loadChatSession();

    launcher.addEventListener("click", (event) => {
      if (Date.now() < state.chat.suppressToggleUntil) {
        event.preventDefault();
        return;
      }
      setChatOpen(!state.chat.open);
    });

    headerBtn?.addEventListener("click", () => {
      setChatOpen(true);
    });

    launcher.addEventListener("pointerdown", (event) => {
      startChatDrag(event, "launcher");
    });

    header?.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button")) return;
      startChatDrag(event, "panel");
    });

    closeBtn?.addEventListener("click", () => {
      setChatOpen(false);
    });

    resetBtn?.addEventListener("click", () => {
      resetChatSession();
    });

    form?.addEventListener("submit", (event) => {
      event.preventDefault();
      sendChatQuestion(input?.value || "");
    });

    input?.addEventListener("input", () => {
      autosizeChatInput();
    });

    input?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendChatQuestion(input.value || "");
      }
    });

    autosizeChatInput();

    document.addEventListener("pointermove", handleChatDragMove);
    document.addEventListener("pointerup", stopChatDrag);
    document.addEventListener("pointercancel", stopChatDrag);
    window.addEventListener("resize", () => {
      applyChatLauncherPosition(state.chat.position);
      positionChatPanel();
    });
  }

  function bindDocumentEvents() {
    document.addEventListener("click", (event) => {
      const dropdown = el("exp-dd");
      if (dropdown && !dropdown.contains(event.target)) {
        dropdown.style.display = "none";
      }
      const profileMenu = el("profile-dd");
      const profileWrap = event.target.closest(".profile-wrap");
      if (profileMenu && !profileWrap) {
        profileMenu.classList.remove("show");
        const trigger = document.querySelector(".profile-trigger");
        if (trigger) trigger.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeModal();
        setChatOpen(false);
        const dropdown = el("exp-dd");
        if (dropdown) dropdown.style.display = "none";
        const profileMenu = el("profile-dd");
        if (profileMenu) profileMenu.classList.remove("show");
        const trigger = document.querySelector(".profile-trigger");
        if (trigger) trigger.setAttribute("aria-expanded", "false");
      }
    });
  }

  function renderAll() {
    const system = state.data?.system || {};
    updateMeta(`ChaqmoqApp CRM - ${formatDateRange(system.start_date, system.end_date)}`);
    syncTabButtons();
    renderTabCounts();
    renderKpis();
    renderRevenueChart();
    renderPaymentBlock();
    renderLeadAnalyticsPanel();
    renderTeachers();
    renderGroups();
  }

  function init() {
    setPeriodUi();
    bindTabs();
    bindFilters();
    bindAiChat();
    bindDocumentEvents();
    tickClock();
    loadDashboard();
  }

  window.setPeriod = setPeriod;
  window.loadDashboard = loadDashboard;
  window.toggleExport = toggleExport;
  window.toggleProfileMenu = toggleProfileMenu;
  window.doExport = doExport;
  window.closeModal = closeModal;
  window.openModalDetail = openModalDetail;

  init();
})();
