(function () {
  const config = window.directorPanelConfig || {};
  const API_URL = config.apiUrl || "";
  const AI_CHAT_URL = config.aiChatUrl || "";
  const AI_CHAT_RESET_URL = config.aiChatResetUrl || "";
  const AI_CHAT_ASK_URL = config.aiChatAskUrl || "";
  const AI_CHAT_POSITION_URL = config.aiChatPositionUrl || "";
  const CURRENT_USER_NAME = config.currentUserName || "Siz";
  const CURRENT_USER_INITIAL = (config.currentUserInitial || CURRENT_USER_NAME || "S").slice(0, 1).toUpperCase();

  const COLORS = {
    cyan: "#38bdf8",
    cyanSoft: "rgba(56, 189, 248, 0.18)",
    amber: "#f59e0b",
    amberSoft: "rgba(245, 158, 11, 0.18)",
    emerald: "#34d399",
    emeraldSoft: "rgba(52, 211, 153, 0.18)",
    rose: "#fb7185",
    roseSoft: "rgba(251, 113, 133, 0.18)",
    violet: "#8b5cf6",
    violetSoft: "rgba(139, 92, 246, 0.18)",
    blue: "#3b82f6",
    blueSoft: "rgba(59, 130, 246, 0.18)",
    white: "#e2e8f0",
    muted: "#94a3b8",
    surface: "#08111f",
  };

  const state = {
    data: null,
    charts: {},
    dashboard: {
      loading: false,
      requestId: 0,
      controller: null,
    },
    chat: {
      open: false,
      initialized: false,
      loading: false,
      messages: [],
      session: null,
      position: readStoredChatPosition(),
      drag: null,
      suppressToggleUntil: 0,
    },
  };

  function el(id) {
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

  function nl2br(value) {
    return escapeHtml(value).replace(/\n/g, "<br>");
  }

  function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
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

  function formatMoney(value) {
    return `${formatInteger(value)} UZS`;
  }

  function formatCompactMoney(value) {
    return `${compactNumber(value)} UZS`;
  }

  function formatPercent(value) {
    if (value === null || value === undefined || value === "") return "—";
    return `${Number(value || 0).toFixed(1)}%`;
  }

  function formatSignedPercent(value) {
    if (value === null || value === undefined || value === "") return "—";
    const num = Number(value || 0);
    return `${num > 0 ? "+" : ""}${num.toFixed(1)}%`;
  }

  function formatMetricValue(value, kind) {
    switch (kind) {
      case "money":
        return formatCompactMoney(value);
      case "pct":
        return formatPercent(value);
      case "pct_signed":
        return formatSignedPercent(value);
      case "number":
      default:
        return formatInteger(value);
    }
  }

  function formatDateIso(value) {
    if (!value) return "—";
    const dateValue = new Date(`${value}T00:00:00`);
    if (Number.isNaN(dateValue.getTime())) return value;
    return new Intl.DateTimeFormat("uz-UZ", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(dateValue);
  }

  function formatDateLabel(value) {
    if (!value) return "";
    return String(value)
      .replace(/\b([A-Z][a-z]{2})\b/g, (match) => match.toLowerCase())
      .replace(/_/g, " ");
  }

  function formatChatTime(value, fallback) {
    if (fallback) return fallback;
    if (!value) return "";
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

  function toneClassForNumber(value) {
    const num = Number(value || 0);
    if (num >= 70) return "tone-danger";
    if (num >= 40) return "tone-warning";
    return "tone-success";
  }

  function toneClassForStatus(status, riskScore) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("risk")) return "tone-danger";
    if (normalized.includes("noaktiv")) return "tone-warning";
    if (Number(riskScore || 0) >= 70) return "tone-danger";
    if (normalized.includes("guruhsiz")) return "tone-info";
    return "tone-success";
  }

  function hexToRgba(hex, alpha) {
    const clean = String(hex || "").replace("#", "");
    if (clean.length !== 6) return `rgba(255,255,255,${alpha})`;
    const intVal = Number.parseInt(clean, 16);
    const r = (intVal >> 16) & 255;
    const g = (intVal >> 8) & 255;
    const b = intVal & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function chartGradient(canvas, color) {
    const ctx = canvas.getContext("2d");
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height || 240);
    gradient.addColorStop(0, hexToRgba(color, 0.32));
    gradient.addColorStop(1, hexToRgba(color, 0.02));
    return gradient;
  }

  function premiumTooltip(callbacks) {
    return {
      backgroundColor: COLORS.surface,
      titleColor: COLORS.white,
      bodyColor: "#dbe7f3",
      borderColor: "rgba(255,255,255,0.12)",
      borderWidth: 1,
      cornerRadius: 14,
      padding: 12,
      displayColors: false,
      titleFont: {
        family: "Inter",
        size: 12,
        weight: "700",
      },
      bodyFont: {
        family: "Inter",
        size: 12,
        weight: "600",
      },
      callbacks: callbacks || {},
    };
  }

  function destroyChart(key) {
    if (state.charts[key]) {
      state.charts[key].destroy();
      delete state.charts[key];
    }
  }

  function upsertChart(key, factory) {
    destroyChart(key);
    state.charts[key] = factory();
    return state.charts[key];
  }

  function buildParamsFromInputs() {
    const params = new URLSearchParams();
    const preset = String(el("periodPreset")?.value || "this_month").trim();
    const dateFrom = String(el("dateFromInput")?.value || "").trim();
    const dateTo = String(el("dateToInput")?.value || "").trim();
    const branch = String(el("branchSelect")?.value || "").trim();
    const teacher = String(el("teacherSelect")?.value || "").trim();
    const category = String(el("categorySelect")?.value || "").trim();

    if (preset === "custom" || (dateFrom && dateTo)) {
      params.set("preset", "custom");
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
    } else {
      params.set("preset", preset || "this_month");
    }

    if (branch) params.set("branch", branch);
    if (teacher) params.set("teacher", teacher);
    if (category) params.set("category", category);

    return params;
  }

  function syncSearchParams(params) {
    const url = new URL(window.location.href);
    url.search = params.toString();
    window.history.replaceState({}, "", url.toString());
  }

  function readSearchParams() {
    return new URLSearchParams(window.location.search);
  }

  function updateCustomDateFields() {
    const preset = String(el("periodPreset")?.value || "this_month").trim();
    const isCustom = preset === "custom";
    ["dateFromInput", "dateToInput"].forEach((id) => {
      const input = el(id);
      if (!input) return;
      input.disabled = !isCustom;
    });
  }

  function applySearchParamsToInputs() {
    const params = readSearchParams();
    const preset = params.get("preset") || "this_month";
    const dateFrom = params.get("date_from") || "";
    const dateTo = params.get("date_to") || "";

    if (el("periodPreset")) el("periodPreset").value = preset;
    if (el("dateFromInput")) el("dateFromInput").value = dateFrom;
    if (el("dateToInput")) el("dateToInput").value = dateTo;
    updateCustomDateFields();
  }

  function fillSelect(selectId, options, selectedValue, placeholderLabel) {
    const select = el(selectId);
    if (!select) return;

    const normalizedSelected = selectedValue === null || selectedValue === undefined ? "" : String(selectedValue);
    const currentValue = normalizedSelected || select.value || "";
    const items = Array.isArray(options) ? options : [];

    select.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = placeholderLabel || "Barchasi";
    select.appendChild(placeholder);

    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = String(item.id);
      option.textContent = item.name;
      if (option.value === currentValue) option.selected = true;
      select.appendChild(option);
    });

    if (currentValue && !items.some((item) => String(item.id) === currentValue)) {
      select.value = "";
    }
  }

  function hydrateFilters(payload) {
    const options = payload?.filters?.options || {};
    const applied = payload?.filters?.applied || {};

    fillSelect("branchSelect", options.branches, (applied.branch_ids || [])[0] || "", "Barchasi");
    fillSelect("teacherSelect", options.teachers, (applied.teacher_ids || [])[0] || "", "Barchasi");
    fillSelect("categorySelect", options.categories, (applied.category_ids || [])[0] || "", "Barchasi");

    if (el("periodPreset")) el("periodPreset").value = applied.preset || "this_month";
    if (el("dateFromInput")) el("dateFromInput").value = applied.date_from || "";
    if (el("dateToInput")) el("dateToInput").value = applied.date_to || "";
    updateCustomDateFields();
  }

  function setDashboardLoading(isLoading) {
    state.dashboard.loading = isLoading;
    const applyButton = el("applyFiltersBtn");
    const resetButton = el("resetFiltersBtn");
    if (applyButton) {
      applyButton.disabled = isLoading;
      applyButton.textContent = isLoading ? "Yuklanmoqda..." : "Yangilash";
    }
    if (resetButton) resetButton.disabled = isLoading;
    if (el("dashboardMeta") && isLoading && !state.data) {
      el("dashboardMeta").textContent = "Panel yuklanmoqda...";
    }
  }

  function hasMeaningfulSeries(values) {
    return Array.isArray(values) && values.some((value) => Number(value || 0) !== 0);
  }

  function toggleChartEmpty(id, message, show) {
    const node = el(id);
    if (!node) return;
    if (message) node.textContent = message;
    node.hidden = !show;
  }

  function setDashboardMeta(payload) {
    const startDate = payload?.system?.start_date;
    const endDate = payload?.system?.end_date;
    const lastUpdated = payload?.system?.last_updated || "--:--:--";
    const meta = `${formatDateIso(startDate)} - ${formatDateIso(endDate)} · ${lastUpdated}`;
    if (el("dashboardMeta")) el("dashboardMeta").textContent = meta;
  }

  function renderTodayStrip(payload) {
    const todayStrip = Array.isArray(payload?.executive?.today_strip) ? payload.executive.today_strip : [];
    const container = el("todayStrip");
    if (!container) return;

    if (!todayStrip.length) {
      container.innerHTML = `
        <div class="dd-empty-state">Bugungi tezkor ko'rsatkichlar topilmadi.</div>
      `;
      return;
    }

    container.innerHTML = todayStrip
      .slice(0, 4)
      .map((item) => {
        const detail = item.detail_kind ? formatMetricValue(item.detail, item.detail_kind) : escapeHtml(item.detail || "");
        return `
          <article class="dd-hero-stat">
            <span>${escapeHtml(item.label || "Ko'rsatkich")}</span>
            <strong>${formatMetricValue(item.value, item.kind)}</strong>
            <small>${detail}</small>
          </article>
        `;
      })
      .join("");

    if (el("heroTrendText")) {
      el("heroTrendText").textContent = payload?.executive?.trend_signal?.text || "Trend signali mavjud emas.";
    }
    if (el("heroSignalTone")) {
      el("heroSignalTone").textContent = payload?.executive?.trend_signal?.title || "Barqaror";
    }
  }

  function appendCurrentFilters(urlValue) {
    if (!urlValue) return "#";
    const url = new URL(urlValue, window.location.origin);
    const params = buildParamsFromInputs();
    params.forEach((value, key) => {
      url.searchParams.set(key, value);
    });
    return `${url.pathname}${url.search}`;
  }

  function syncShortcutLinks() {
    document.querySelectorAll("[data-link-key]").forEach((anchor) => {
      const key = anchor.getAttribute("data-link-key");
      const baseUrl = config?.links?.[key];
      if (!baseUrl) return;
      anchor.setAttribute("href", appendCurrentFilters(baseUrl));
    });
  }

  function renderShortcutCounts(payload) {
    if (el("tab-count-manager")) el("tab-count-manager").textContent = `${formatInteger(payload?.managers?.total_count)} manager`;
    if (el("tab-count-teachers")) el("tab-count-teachers").textContent = `${formatInteger(payload?.teachers?.total_count)} ustoz`;
    if (el("tab-count-students")) el("tab-count-students").textContent = `${formatInteger(payload?.students?.active_students)} o'quvchi`;
    if (el("tab-count-products")) el("tab-count-products").textContent = `${formatInteger(payload?.requests?.products_count)} mahsulot`;
    if (el("tab-count-requests")) el("tab-count-requests").textContent = `${formatInteger(payload?.requests?.total_count)} so'rov`;
  }

  function sparklineSeriesFromPayload(payload) {
    const teachers = Array.isArray(payload?.teachers?.ranking)
      ? payload.teachers.ranking.slice(0, 8).map((item) => Number(item.revenue || 0))
      : [];
    const attendance = Array.isArray(payload?.groups?.profitability)
      ? payload.groups.profitability
          .filter((item) => item && item.attendance_rate !== null && item.attendance_rate !== undefined)
          .slice(0, 8)
          .map((item) => Number(item.attendance_rate || 0))
      : [];

    return {
      students: Array.isArray(payload?.charts?.new_students) ? payload.charts.new_students : [],
      teachers,
      income: Array.isArray(payload?.charts?.income) ? payload.charts.income : [],
      attendance,
    };
  }

  function renderSparkline(chartKey, canvasId, values, color) {
    const canvas = el(canvasId);
    if (!canvas || !window.Chart) return;
    const points = Array.isArray(values) && values.length ? values : [0, 0, 0, 0];

    upsertChart(chartKey, () => {
      const ctx = canvas.getContext("2d");
      return new Chart(ctx, {
        type: "line",
        data: {
          labels: points.map((_, index) => index + 1),
          datasets: [
            {
              data: points,
              borderColor: color,
              backgroundColor: chartGradient(canvas, color),
              borderWidth: 2.2,
              fill: true,
              tension: 0.4,
              pointRadius: 0,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { enabled: false },
          },
          scales: {
            x: { display: false },
            y: { display: false },
          },
          interaction: {
            intersect: false,
            mode: "index",
          },
        },
      });
    });
  }

  function renderKpis(payload) {
    const spark = sparklineSeriesFromPayload(payload);
    const studentsTotal = payload?.students?.total || 0;
    const activeStudents = payload?.students?.active_students || 0;
    const inactiveStudents = payload?.students?.inactive_students || 0;
    const teachersTotal = payload?.teachers?.total_count || 0;
    const teachersRisk = Array.isArray(payload?.teachers?.at_risk) ? payload.teachers.at_risk.length : 0;
    const income = payload?.finance?.income || 0;
    const profit = payload?.finance?.profit || 0;
    const attendanceRate = payload?.overview?.kpis?.attendance_rate;
    const completionRate = payload?.finance?.payment_completion_rate;

    if (el("kpiStudentsValue")) el("kpiStudentsValue").textContent = formatInteger(studentsTotal);
    if (el("kpiStudentsMeta")) el("kpiStudentsMeta").textContent = `Faol ${formatInteger(activeStudents)} · Noaktiv ${formatInteger(inactiveStudents)}`;
    if (el("kpiStudentsDelta")) el("kpiStudentsDelta").textContent = formatSignedPercent(payload?.students?.growth_pct || 0);

    if (el("kpiTeachersValue")) el("kpiTeachersValue").textContent = formatInteger(teachersTotal);
    if (el("kpiTeachersMeta")) el("kpiTeachersMeta").textContent = `Risk ${formatInteger(teachersRisk)} · Top ${formatInteger((payload?.teachers?.top || []).length)}`;
    if (el("kpiTeachersDelta")) el("kpiTeachersDelta").textContent = `${formatInteger((payload?.teachers?.top || []).length)} top`;

    if (el("kpiIncomeValue")) el("kpiIncomeValue").textContent = formatCompactMoney(income);
    if (el("kpiIncomeMeta")) el("kpiIncomeMeta").textContent = `Foyda ${formatCompactMoney(profit)}`;
    if (el("kpiIncomeDelta")) el("kpiIncomeDelta").textContent = formatSignedPercent(payload?.finance?.income_growth || 0);

    if (el("kpiAttendanceValue")) el("kpiAttendanceValue").textContent = formatPercent(attendanceRate);
    if (el("kpiAttendanceMeta")) el("kpiAttendanceMeta").textContent = `To'lov bajarildi ${formatPercent(completionRate)}`;
    if (el("kpiAttendanceDelta")) {
      const trendValue = Number(attendanceRate || 0) - Number(completionRate || 0);
      el("kpiAttendanceDelta").textContent = formatSignedPercent(trendValue);
    }

    renderSparkline("sparkStudents", "studentsSpark", spark.students, COLORS.cyan);
    renderSparkline("sparkTeachers", "teachersSpark", spark.teachers, COLORS.violet);
    renderSparkline("sparkIncome", "forecast-chart", spark.income, COLORS.amber);
    renderSparkline("sparkAttendance", "attendanceSpark", spark.attendance, COLORS.emerald);
  }

  function renderFinanceChart(payload) {
    const canvas = el("rev-chart");
    if (!canvas || !window.Chart) return;

    const labels = Array.isArray(payload?.charts?.labels) ? payload.charts.labels : [];
    const income = Array.isArray(payload?.charts?.income) ? payload.charts.income : [];
    const expenses = Array.isArray(payload?.charts?.expenses) ? payload.charts.expenses : [];
    const hasData = labels.length && (hasMeaningfulSeries(income) || hasMeaningfulSeries(expenses));

    const legendNode = el("rev-legend");
    if (legendNode) {
      legendNode.innerHTML = `
        <span class="dd-legend-item"><span class="dd-legend-dot" style="background:${COLORS.blue};"></span>Daromad</span>
        <span class="dd-legend-item"><span class="dd-legend-dot" style="background:${COLORS.amber};"></span>Xarajat</span>
      `;
    }

    toggleChartEmpty("revChartEmpty", "Tanlangan davr uchun to'lov grafigi topilmadi.", !hasData);
    if (!hasData) {
      destroyChart("financeMain");
      const summaryNode = el("financeSummary");
      if (summaryNode) {
        summaryNode.innerHTML = `<div class="dd-summary-pill">Tanlangan davr uchun moliyaviy qatorlar topilmadi.</div>`;
      }
      return;
    }

    upsertChart("financeMain", () => {
      return new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
          labels: labels.map(formatDateLabel),
          datasets: [
            {
              label: "Daromad",
              data: income,
              borderColor: COLORS.blue,
              backgroundColor: chartGradient(canvas, COLORS.blue),
              pointRadius: 0,
              pointHoverRadius: 4,
              borderWidth: 2.6,
              fill: true,
              tension: 0.4,
            },
            {
              label: "Xarajat",
              data: expenses,
              borderColor: COLORS.amber,
              backgroundColor: hexToRgba(COLORS.amber, 0.06),
              pointRadius: 0,
              pointHoverRadius: 4,
              borderWidth: 2,
              fill: false,
              tension: 0.4,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: "index",
            intersect: false,
          },
          plugins: {
            legend: { display: false },
            tooltip: premiumTooltip({
              label(context) {
                return `${context.dataset.label}: ${formatCompactMoney(context.parsed.y)}`;
              },
            }),
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: {
                color: COLORS.muted,
                maxRotation: 0,
              },
              border: { color: "rgba(255,255,255,0.08)" },
            },
            y: {
              ticks: {
                color: COLORS.muted,
                callback(value) {
                  return compactNumber(value);
                },
              },
              grid: {
                color: "rgba(255,255,255,0.06)",
                drawBorder: false,
              },
              border: { display: false },
            },
          },
        },
      });
    });

    const summaryNode = el("financeSummary");
    if (summaryNode) {
      summaryNode.innerHTML = [
        ["Daromad", formatCompactMoney(payload?.finance?.income)],
        ["Sof foyda", formatCompactMoney(payload?.finance?.profit)],
        ["Ochiq qarz", formatCompactMoney(payload?.finance?.open_debt)],
        ["O'rtacha to'lov", formatCompactMoney(payload?.finance?.avg_payment)],
      ]
        .map(
          ([label, value]) => `
            <span class="dd-summary-pill">
              <small>${escapeHtml(label)}</small>
              <strong>${escapeHtml(value)}</strong>
            </span>
          `
        )
        .join("");
    }
  }

  function buildAttendanceBreakdown(payload) {
    const profitability = Array.isArray(payload?.groups?.profitability) ? payload.groups.profitability : [];
    const ranked = profitability
      .filter((item) => item && item.attendance_rate !== null && item.attendance_rate !== undefined)
      .sort((left, right) => Number(right.attendance_rate || 0) - Number(left.attendance_rate || 0))
      .slice(0, 6);

    return {
      labels: ranked.map((item) => item.group_name),
      values: ranked.map((item) => Number(item.attendance_rate || 0)),
    };
  }

  function renderAttendanceChart(payload) {
    const canvas = el("donut-chart");
    if (!canvas || !window.Chart) return;

    const { labels, values } = buildAttendanceBreakdown(payload);
    const hasData = labels.length && hasMeaningfulSeries(values);

    toggleChartEmpty("attendanceChartEmpty", "Davomat grafigi uchun yetarli ma'lumot topilmadi.", !hasData);
    if (!hasData) {
      destroyChart("attendanceMain");
      return;
    }

    upsertChart("attendanceMain", () => {
      return new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
          labels,
          datasets: [
            {
              label: "Davomat",
              data: values,
              backgroundColor: labels.map((_, index) =>
                [COLORS.emeraldSoft, COLORS.cyanSoft, COLORS.violetSoft, COLORS.blueSoft, COLORS.amberSoft, COLORS.roseSoft][index % 6]
              ),
              borderColor: labels.map((_, index) =>
                [COLORS.emerald, COLORS.cyan, COLORS.violet, COLORS.blue, COLORS.amber, COLORS.rose][index % 6]
              ),
              borderWidth: 1.6,
              borderRadius: 12,
              borderSkipped: false,
              maxBarThickness: 34,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: premiumTooltip({
              label(context) {
                return `Davomat: ${formatPercent(context.parsed.y)}`;
              },
            }),
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: {
                color: COLORS.muted,
                maxRotation: 0,
                autoSkip: false,
                callback(value, index) {
                  const label = labels[index] || "";
                  return label.length > 12 ? `${label.slice(0, 12)}...` : label;
                },
              },
              border: { color: "rgba(255,255,255,0.08)" },
            },
            y: {
              min: 0,
              max: 100,
              ticks: {
                color: COLORS.muted,
                callback(value) {
                  return `${value}%`;
                },
              },
              grid: {
                color: "rgba(255,255,255,0.06)",
                drawBorder: false,
              },
              border: { display: false },
            },
          },
        },
      });
    });
  }

  function renderRiskList(payload) {
    const node = el("churn-risk-list");
    if (!node) return;

    const items = Array.isArray(payload?.students?.risk_students) ? payload.students.risk_students.slice(0, 5) : [];
    const dangerCount = items.filter((item) => Number(item.risk_score || 0) >= 70).length;
    const riskLabel = dangerCount ? `${dangerCount} ta yuqori risk` : "Risk nazoratda";

    if (el("churnSummaryChip")) {
      el("churnSummaryChip").textContent = riskLabel;
      el("churnSummaryChip").className = `dd-pill ${dangerCount ? "tone-danger" : "dd-pill-muted"}`;
    }

    if (!items.length) {
      node.innerHTML = `<div class="dd-empty-state">Hozircha risk talab qiladigan o'quvchilar topilmadi.</div>`;
      return;
    }

    node.innerHTML = items
      .map((item) => {
        const score = Number(item.risk_score || item.status || 0);
        return `
          <article class="dd-risk-item">
            <div class="dd-risk-top">
              <strong>${escapeHtml(item.name)}</strong>
              <span class="dd-risk-score ${toneClassForNumber(score)}">${formatInteger(score)} ball</span>
            </div>
            <div class="dd-risk-meta">${escapeHtml(item.course || "Guruhsiz")}</div>
            <div class="dd-risk-meta">${escapeHtml(item.reason || "Qo'shimcha signal mavjud emas")}</div>
          </article>
        `;
      })
      .join("");
  }

  function parseUzDate(value) {
    const match = String(value || "").match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (!match) return 0;
    return new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1])).getTime();
  }

  function sortedRoster(payload) {
    const roster = Array.isArray(payload?.students?.roster) ? [...payload.students.roster] : [];
    return roster.sort((left, right) => parseUzDate(right.joined_at) - parseUzDate(left.joined_at));
  }

  function renderRecentTable(payload) {
    const tbody = el("recentActivityBody");
    if (!tbody) return;

    const rows = sortedRoster(payload).slice(0, 8);
    if (el("tableMeta")) {
      el("tableMeta").textContent = `${formatInteger((payload?.students?.roster || []).length)} ta yozuv`;
    }

    if (!rows.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6">
            <div class="dd-empty-state">O'quvchi jadvali uchun ma'lumot topilmadi.</div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = rows
      .map((item) => {
        return `
          <tr>
            <td>
              <strong>${escapeHtml(item.name)}</strong>
              <small>Risk ${formatInteger(item.risk_score || 0)} ball</small>
            </td>
            <td>${escapeHtml(item.course || "Guruhsiz")}</td>
            <td>${escapeHtml(item.joined_at || "—")}</td>
            <td>${escapeHtml(item.attendance_pct || "—")}</td>
            <td>${formatCompactMoney(item.debt || 0)}</td>
            <td>
              <span class="dd-status-chip ${toneClassForStatus(item.status_label, item.risk_score)}">
                ${escapeHtml(item.status_label || "Noma'lum")}
              </span>
            </td>
          </tr>
        `;
      })
      .join("");
  }

  function buildModalMarkup(payload) {
    const risks = Array.isArray(payload?.students?.risk_students) ? payload.students.risk_students : [];
    if (!risks.length) {
      return `<div class="dd-empty-state">Batafsil risk ro'yxati mavjud emas.</div>`;
    }

    return risks
      .slice(0, 16)
      .map((item) => {
        return `
          <article class="dd-modal-list-item">
            <strong>${escapeHtml(item.name)}</strong>
            <div class="dd-modal-muted">${escapeHtml(item.course || "Guruhsiz")}</div>
            <div class="dd-modal-muted">${escapeHtml(item.reason || "Qo'shimcha signal mavjud emas")}</div>
            <div class="dd-modal-muted">Risk: ${formatInteger(item.risk_score || 0)} ball · Qarz: ${formatCompactMoney(item.debt || 0)}</div>
          </article>
        `;
      })
      .join("");
  }

  function openDetailModal() {
    if (!state.data) return;
    if (el("modal-title")) el("modal-title").textContent = "Xavfdagi o'quvchilar ro'yxati";
    if (el("modal-body")) el("modal-body").innerHTML = buildModalMarkup(state.data);
    const modal = el("kpi-modal");
    if (modal) modal.hidden = false;
  }

  function closeDetailModal() {
    const modal = el("kpi-modal");
    if (modal) modal.hidden = true;
  }

  function renderDashboard(payload) {
    state.data = payload;
    hydrateFilters(payload);
    syncSearchParams(buildParamsFromInputs());
    syncShortcutLinks();
    setDashboardMeta(payload);
    renderTodayStrip(payload);
    renderShortcutCounts(payload);
    renderKpis(payload);
    renderFinanceChart(payload);
    renderAttendanceChart(payload);
    renderRiskList(payload);
    renderRecentTable(payload);
  }

  async function loadDashboard() {
    const params = buildParamsFromInputs();
    syncSearchParams(params);
    syncShortcutLinks();
    state.dashboard.requestId += 1;
    const requestId = state.dashboard.requestId;

    if (state.dashboard.controller) {
      state.dashboard.controller.abort();
    }
    state.dashboard.controller = new AbortController();
    setDashboardLoading(true);

    try {
      const response = await fetch(`${API_URL}?${params.toString()}`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
        signal: state.dashboard.controller.signal,
      });
      if (!response.ok) throw new Error(`Dashboard fetch failed: ${response.status}`);
      const payload = await response.json();
      if (requestId !== state.dashboard.requestId) return;
      renderDashboard(payload);
    } catch (error) {
      if (error.name === "AbortError") return;
      console.error(error);
      const message = "Dashboard ma'lumotlarini yuklashda xatolik yuz berdi.";
      if (el("heroTrendText")) el("heroTrendText").textContent = message;
      if (el("recentActivityBody")) {
        el("recentActivityBody").innerHTML = `
          <tr>
            <td colspan="6"><div class="dd-empty-state">${escapeHtml(message)}</div></td>
          </tr>
        `;
      }
      if (el("churn-risk-list")) {
        el("churn-risk-list").innerHTML = `<div class="dd-empty-state">${escapeHtml(message)}</div>`;
      }
      toggleChartEmpty("revChartEmpty", message, true);
      toggleChartEmpty("attendanceChartEmpty", message, true);
      destroyChart("financeMain");
      destroyChart("attendanceMain");
    } finally {
      if (requestId === state.dashboard.requestId) {
        state.dashboard.controller = null;
        setDashboardLoading(false);
      }
    }
  }

  function setChatStatus(text, muted) {
    const status = el("directorAiChatStatus");
    if (!status) return;
    status.textContent = text;
    status.className = muted
      ? "director-ai-chat-chip director-ai-chat-chip-muted"
      : "director-ai-chat-chip";
  }

  function renderChatMessages() {
    const container = el("directorAiChatMessages");
    if (!container) return;

    if (!state.chat.messages.length) {
      container.innerHTML = `
        <div id="directorAiChatEmpty" class="director-ai-chat-empty">
          Masalan: "Eng qarzdor guruh qaysi?", "Qaysi lead manbasi yaxshi ishlayapti?", "Davomat nima uchun pasaydi?"
        </div>
      `;
      return;
    }

    container.innerHTML = state.chat.messages
      .map((message) => {
        const role = String(message.role || "").toLowerCase();
        const isUser = role === "user";
        const timeText = formatChatTime(message.created_at, message.created_label);
        return `
          <div class="director-ai-chat-message ${isUser ? "user" : "assistant"}">
            <div class="director-ai-chat-avatar ${isUser ? "user" : ""}">
              ${isUser ? escapeHtml(CURRENT_USER_INITIAL) : "AI"}
            </div>
            <div class="director-ai-chat-bubble">
              <p>${nl2br(message.content)}</p>
              <div class="director-ai-chat-message-meta">${escapeHtml(timeText)}</div>
            </div>
          </div>
        `;
      })
      .join("");

    container.scrollTop = container.scrollHeight;
  }

  function readStoredChatPosition() {
    try {
      const raw = localStorage.getItem("director-ai-chat-position");
      if (!raw) return { x: null, y: null };
      const parsed = JSON.parse(raw);
      return {
        x: parsed && Number.isFinite(parsed.x) ? parsed.x : null,
        y: parsed && Number.isFinite(parsed.y) ? parsed.y : null,
      };
    } catch (error) {
      return { x: null, y: null };
    }
  }

  function storeChatPosition(position) {
    try {
      localStorage.setItem("director-ai-chat-position", JSON.stringify(position));
    } catch (error) {
      console.warn("Chat position store failed", error);
    }
  }

  function defaultChatPosition() {
    return {
      x: window.innerWidth - 92,
      y: window.innerHeight - 92,
    };
  }

  function clampChatPosition(x, y) {
    const maxX = Math.max(12, window.innerWidth - 76);
    const maxY = Math.max(12, window.innerHeight - 76);
    return {
      x: Math.min(Math.max(Math.round(x), 12), maxX),
      y: Math.min(Math.max(Math.round(y), 12), maxY),
    };
  }

  function currentChatAnchor() {
    const fallback = defaultChatPosition();
    const x = state.chat.position.x;
    const y = state.chat.position.y;
    return clampChatPosition(
      Number.isFinite(x) ? x : fallback.x,
      Number.isFinite(y) ? y : fallback.y
    );
  }

  function applyChatPosition() {
    const launcher = el("directorAiChatLauncher");
    const panel = el("directorAiChatPanel");
    if (!launcher || !panel) return;

    if (window.innerWidth <= 767) {
      launcher.style.left = "";
      launcher.style.top = "";
      launcher.style.right = "12px";
      launcher.style.bottom = "12px";
      panel.style.left = "";
      panel.style.top = "";
      panel.style.right = "12px";
      panel.style.bottom = "76px";
      return;
    }

    const anchor = currentChatAnchor();
    launcher.style.left = `${anchor.x}px`;
    launcher.style.top = `${anchor.y}px`;
    launcher.style.right = "auto";
    launcher.style.bottom = "auto";

    const panelWidth = Math.min(380, window.innerWidth - 24);
    const panelHeight = Math.min(620, window.innerHeight - 120);
    let left = anchor.x - panelWidth + 56;
    let top = anchor.y - panelHeight + 56;

    left = Math.min(Math.max(left, 12), window.innerWidth - panelWidth - 12);
    top = Math.min(Math.max(top, 12), window.innerHeight - panelHeight - 12);

    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
  }

  async function persistChatPosition() {
    if (!AI_CHAT_POSITION_URL) return;
    try {
      await fetch(AI_CHAT_POSITION_URL, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({
          position: {
            x: state.chat.position.x,
            y: state.chat.position.y,
          },
        }),
      });
    } catch (error) {
      console.warn("Chat position sync failed", error);
    }
  }

  function beginChatDrag(event, source) {
    if (window.innerWidth <= 767) return;
    if (source === "panel" && event.target.closest("button")) return;

    const launcher = el("directorAiChatLauncher");
    const panel = el("directorAiChatPanel");
    const anchor = currentChatAnchor();

    if (source === "launcher") {
      const rect = launcher.getBoundingClientRect();
      state.chat.drag = {
        source,
        offsetX: event.clientX - rect.left,
        offsetY: event.clientY - rect.top,
        moved: false,
      };
    } else if (panel) {
      const rect = panel.getBoundingClientRect();
      state.chat.drag = {
        source,
        offsetX: event.clientX - rect.left,
        offsetY: event.clientY - rect.top,
        width: rect.width,
        height: rect.height,
        moved: false,
      };
    } else {
      state.chat.drag = {
        source,
        offsetX: event.clientX - anchor.x,
        offsetY: event.clientY - anchor.y,
        moved: false,
      };
    }

    const header = el("directorAiChatHeader");
    if (header && source === "panel") header.classList.add("is-dragging");

    document.addEventListener("pointermove", onChatDrag);
    document.addEventListener("pointerup", endChatDrag);
  }

  function onChatDrag(event) {
    if (!state.chat.drag) return;
    state.chat.drag.moved = true;

    let nextPosition;
    if (state.chat.drag.source === "panel") {
      const width = state.chat.drag.width || 380;
      const height = state.chat.drag.height || 520;
      const left = event.clientX - state.chat.drag.offsetX;
      const top = event.clientY - state.chat.drag.offsetY;
      nextPosition = clampChatPosition(left + width - 56, top + height - 56);
    } else {
      nextPosition = clampChatPosition(
        event.clientX - state.chat.drag.offsetX,
        event.clientY - state.chat.drag.offsetY
      );
    }

    state.chat.position = nextPosition;
    storeChatPosition(nextPosition);
    applyChatPosition();
  }

  function endChatDrag() {
    document.removeEventListener("pointermove", onChatDrag);
    document.removeEventListener("pointerup", endChatDrag);

    const header = el("directorAiChatHeader");
    if (header) header.classList.remove("is-dragging");

    if (state.chat.drag) {
      if (state.chat.drag.moved) {
        state.chat.suppressToggleUntil = Date.now() + 250;
      }
      state.chat.drag = null;
      persistChatPosition();
    }
  }

  function updateChatVisibility() {
    const panel = el("directorAiChatPanel");
    const launcher = el("directorAiChatLauncher");
    const headerBtn = el("directorAiChatHeaderBtn");
    if (!panel || !launcher || !headerBtn) return;

    panel.setAttribute("aria-hidden", state.chat.open ? "false" : "true");
    launcher.classList.toggle("is-hidden", state.chat.open);
    launcher.setAttribute("aria-expanded", state.chat.open ? "true" : "false");
    headerBtn.setAttribute("aria-expanded", state.chat.open ? "true" : "false");
  }

  function openChat(forceState) {
    const shouldOpen = typeof forceState === "boolean" ? forceState : !state.chat.open;
    state.chat.open = shouldOpen;
    updateChatVisibility();
    applyChatPosition();
    if (shouldOpen && !state.chat.initialized) {
      loadChat();
    }
    if (shouldOpen) {
      requestAnimationFrame(() => {
        if (el("directorAiChatInput")) el("directorAiChatInput").focus();
      });
    }
  }

  async function loadChat() {
    if (!AI_CHAT_URL || state.chat.loading) return;
    state.chat.loading = true;
    setChatStatus("Chat yuklanmoqda...", true);

    try {
      const response = await fetch(AI_CHAT_URL, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error(`Chat fetch failed: ${response.status}`);
      const payload = await response.json();

      state.chat.messages = Array.isArray(payload.messages) ? payload.messages : [];
      state.chat.session = payload.session || null;
      state.chat.initialized = true;

      const position = payload?.session?.launcher_position || {};
      if (position.x !== null && position.x !== undefined && position.y !== null && position.y !== undefined) {
        state.chat.position = clampChatPosition(position.x, position.y);
        storeChatPosition(state.chat.position);
      }

      renderChatMessages();
      applyChatPosition();
      setChatStatus("Tarix saqlanadi", true);
    } catch (error) {
      console.error(error);
      setChatStatus("Chat vaqtincha ulanmayapti", true);
    } finally {
      state.chat.loading = false;
    }
  }

  async function resetChat() {
    if (!AI_CHAT_RESET_URL) return;
    setChatStatus("Chat tozalanmoqda...", true);
    try {
      const response = await fetch(AI_CHAT_RESET_URL, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({}),
      });
      if (!response.ok) throw new Error(`Chat reset failed: ${response.status}`);
      const payload = await response.json();
      state.chat.messages = Array.isArray(payload.messages) ? payload.messages : [];
      state.chat.session = payload.session || null;
      renderChatMessages();
      setChatStatus("Chat tozalandi", true);
    } catch (error) {
      console.error(error);
      setChatStatus("Tozalashda xatolik", true);
    }
  }

  async function askChat(question) {
    if (!AI_CHAT_ASK_URL || !question) return;
    setChatStatus("Javob tayyorlanmoqda...", false);
    state.chat.loading = true;
    const submitButton = el("directorAiChatSend");
    const input = el("directorAiChatInput");
    if (submitButton) submitButton.disabled = true;
    if (input) input.disabled = true;

    try {
      const response = await fetch(AI_CHAT_ASK_URL, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ question }),
      });
      if (!response.ok) throw new Error(`Chat ask failed: ${response.status}`);
      const payload = await response.json();

      if (payload.user_message) state.chat.messages.push(payload.user_message);
      if (payload.assistant_message) state.chat.messages.push(payload.assistant_message);
      state.chat.session = payload.session || state.chat.session;
      renderChatMessages();
      setChatStatus("Tarix saqlanadi", true);
    } catch (error) {
      console.error(error);
      setChatStatus("Javob olishda xatolik", true);
    } finally {
      state.chat.loading = false;
      if (submitButton) submitButton.disabled = false;
      if (input) {
        input.disabled = false;
        input.focus();
      }
    }
  }

  function autosizeTextarea() {
    const input = el("directorAiChatInput");
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
  }

  function bindProfileMenu() {
    const trigger = el("profileTrigger");
    const menu = el("profile-dd");
    if (!trigger || !menu) return;

    trigger.addEventListener("click", () => {
      const isHidden = menu.hasAttribute("hidden");
      if (isHidden) {
        menu.removeAttribute("hidden");
        trigger.setAttribute("aria-expanded", "true");
      } else {
        menu.setAttribute("hidden", "");
        trigger.setAttribute("aria-expanded", "false");
      }
    });

    document.addEventListener("click", (event) => {
      if (menu.hasAttribute("hidden")) return;
      if (event.target === trigger || trigger.contains(event.target)) return;
      if (menu.contains(event.target)) return;
      menu.setAttribute("hidden", "");
      trigger.setAttribute("aria-expanded", "false");
    });
  }

  function bindFilters() {
    const applyButton = el("applyFiltersBtn");
    const resetButton = el("resetFiltersBtn");
    const presetSelect = el("periodPreset");
    const dateInputs = [el("dateFromInput"), el("dateToInput")].filter(Boolean);

    if (applyButton) applyButton.addEventListener("click", loadDashboard);
    if (resetButton) {
      resetButton.addEventListener("click", () => {
        if (el("periodPreset")) el("periodPreset").value = "this_month";
        if (el("dateFromInput")) el("dateFromInput").value = "";
        if (el("dateToInput")) el("dateToInput").value = "";
        if (el("branchSelect")) el("branchSelect").value = "";
        if (el("teacherSelect")) el("teacherSelect").value = "";
        if (el("categorySelect")) el("categorySelect").value = "";
        updateCustomDateFields();
        loadDashboard();
      });
    }

    if (presetSelect) {
      presetSelect.addEventListener("change", () => {
        if (presetSelect.value !== "custom") {
          if (el("dateFromInput")) el("dateFromInput").value = "";
          if (el("dateToInput")) el("dateToInput").value = "";
        }
        updateCustomDateFields();
      });
    }

    dateInputs.forEach((input) => {
      input.addEventListener("change", () => {
        if (el("periodPreset")) el("periodPreset").value = "custom";
      });
    });
  }

  function bindModal() {
    const openBtn = el("modal-detail-btn");
    const closeBtn = el("modalCloseBtn");
    if (openBtn) openBtn.addEventListener("click", openDetailModal);
    if (closeBtn) closeBtn.addEventListener("click", closeDetailModal);

    document.querySelectorAll("[data-close-modal]").forEach((node) => {
      node.addEventListener("click", closeDetailModal);
    });
  }

  function bindChat() {
    const launcher = el("directorAiChatLauncher");
    const headerBtn = el("directorAiChatHeaderBtn");
    const panelHeader = el("directorAiChatHeader");
    const closeBtn = el("directorAiChatClose");
    const resetBtn = el("directorAiChatReset");
    const form = el("directorAiChatForm");
    const input = el("directorAiChatInput");

    if (launcher) {
      launcher.addEventListener("click", () => {
        if (Date.now() < state.chat.suppressToggleUntil) return;
        openChat(true);
      });
      launcher.addEventListener("pointerdown", (event) => beginChatDrag(event, "launcher"));
    }

    if (headerBtn) headerBtn.addEventListener("click", () => openChat(!state.chat.open));
    if (closeBtn) closeBtn.addEventListener("click", () => openChat(false));
    if (resetBtn) resetBtn.addEventListener("click", resetChat);

    if (panelHeader) {
      panelHeader.addEventListener("pointerdown", (event) => beginChatDrag(event, "panel"));
    }

    if (form) {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const question = String(input?.value || "").trim();
        if (!question || state.chat.loading) return;
        input.value = "";
        autosizeTextarea();
        await askChat(question);
      });
    }

    if (input) {
      input.addEventListener("input", autosizeTextarea);
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          if (form) form.requestSubmit();
        }
      });
    }
  }

  function bindGlobalEvents() {
    window.addEventListener("resize", () => {
      applyChatPosition();
      Object.values(state.charts).forEach((chart) => chart.resize());
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeDetailModal();
        if (state.chat.open) openChat(false);
      }
    });
  }

  async function init() {
    bindProfileMenu();
    bindFilters();
    bindModal();
    bindChat();
    bindGlobalEvents();
    applySearchParamsToInputs();
    updateChatVisibility();
    applyChatPosition();
    await loadDashboard();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
