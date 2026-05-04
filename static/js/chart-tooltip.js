/* ChaqmoqApp — reusable donut/pie tooltip
 * Installs a global Chart.js plugin that replaces the default tooltip
 * for `doughnut` and `pie` charts with an HTML tooltip rendered inside
 * the chart container at a corner that does NOT cover the donut center
 * (where the "JAMI" / total label usually sits).
 *
 * Also exposes window.ChaqmoqDonutTooltip.apexCustom for ApexCharts.
 *
 * Safety: every plugin hook is wrapped in try/catch so a tooltip bug can
 * NEVER prevent a chart from rendering.
 */
(function () {
  'use strict';

  var nfmt;
  try { nfmt = new Intl.NumberFormat('uz-UZ'); }
  catch (e) { nfmt = { format: function (n) { return String(Math.round(Number(n) || 0)); } }; }

  function fmtNumber(value) {
    var n = Number(value);
    if (!isFinite(n)) return String(value == null ? '' : value);
    return nfmt.format(Math.round(n));
  }

  function escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function pickColor(dataPoint, dataset, index) {
    try {
      var bg = dataPoint && dataPoint.element && dataPoint.element.options && dataPoint.element.options.backgroundColor;
      if (bg && typeof bg === 'string') return bg;
      var dsBg = dataset && dataset.backgroundColor;
      if (Array.isArray(dsBg)) return dsBg[index] || dsBg[0] || '#38bdf8';
      if (typeof dsBg === 'string') return dsBg;
    } catch (e) {}
    return '#38bdf8';
  }

  function ensureContainerPositioned(parent) {
    if (!parent || !parent.style) return;
    var cs = window.getComputedStyle(parent);
    if (cs && cs.position === 'static') parent.style.position = 'relative';
  }

  function ensureTooltipEl(chart) {
    var parent = chart && chart.canvas && chart.canvas.parentNode;
    if (!parent) return null;
    ensureContainerPositioned(parent);
    var sel = '.chq-tooltip[data-chart-tooltip="' + chart.id + '"]';
    var el = null;
    try { el = parent.querySelector(sel); } catch (e) { el = null; }
    if (el && el.parentNode !== parent) el = null;
    if (!el) {
      el = document.createElement('div');
      el.className = 'chq-tooltip';
      el.setAttribute('data-chart-tooltip', String(chart.id));
      el.setAttribute('role', 'tooltip');
      parent.appendChild(el);
    }
    return el;
  }

  function metaKindFor(dataset) {
    if (!dataset) return 'count';
    return dataset.metaKind || dataset.chqKind || 'count';
  }

  function formatValueByKind(value, kind) {
    var n = Number(value || 0);
    if (kind === 'money') return fmtNumber(n) + " so'm";
    if (kind === 'money-short') {
      if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(1).replace(/\.0$/, '') + " mlrd so'm";
      if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, '') + " mln so'm";
      if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, '') + " ming so'm";
      return fmtNumber(n) + " so'm";
    }
    if (kind === 'percent') return n.toFixed(1) + '%';
    if (kind === 'hours') return Math.round(n) + ' soat';
    return fmtNumber(n);
  }

  function placeTooltip(el, chart) {
    var parent = chart && chart.canvas && chart.canvas.parentNode;
    if (!parent) return;
    var pw = parent.clientWidth || 0;
    var ph = parent.clientHeight || 0;
    el.classList.remove('chq-tt-mobile', 'chq-tt-corner-tl');
    if (pw < 320 || ph < 200) {
      el.classList.add('chq-tt-mobile');
      return;
    }
    el.classList.add('chq-tt-corner-tl');
  }

  function externalTooltipHandler(context) {
    try {
      var chart = context && context.chart;
      var tooltip = context && context.tooltip;
      if (!chart) return;
      var el = ensureTooltipEl(chart);
      if (!el) return;

      if (!tooltip || !tooltip.opacity) {
        el.classList.remove('chq-tt-show');
        return;
      }

      var dp = (tooltip.dataPoints && tooltip.dataPoints[0]) || null;
      if (!dp) {
        el.classList.remove('chq-tt-show');
        return;
      }

      var dataset = dp.dataset
        || (chart.data && chart.data.datasets && chart.data.datasets[dp.datasetIndex])
        || {};
      var idx = (typeof dp.dataIndex === 'number') ? dp.dataIndex : 0;
      var dataArr = (dataset && dataset.data) || [];
      var rawValue = Number(dataArr[idx] || 0);

      var total = 0;
      for (var i = 0; i < dataArr.length; i++) total += Number(dataArr[i] || 0);
      var pct = total ? (rawValue / total) * 100 : 0;

      var label = dp.label;
      if (label == null) label = (chart.data && chart.data.labels && chart.data.labels[idx]) || '';
      var color = pickColor(dp, dataset, idx);
      var kind = metaKindFor(dataset);
      var valueText = formatValueByKind(rawValue, kind);

      el.innerHTML =
        '<div class="chq-tt-row">' +
          '<span class="chq-tt-dot" style="background:' + escapeHtml(color) + '"></span>' +
          '<span class="chq-tt-label">' + escapeHtml(label) + '</span>' +
        '</div>' +
        '<div class="chq-tt-value">' + escapeHtml(valueText) + '</div>' +
        '<div class="chq-tt-pct">Ulushi: <strong>' + pct.toFixed(1) + '%</strong></div>';

      placeTooltip(el, chart);
      el.classList.add('chq-tt-show');
    } catch (e) {
      try { console && console.warn && console.warn('chqDonutTooltip:', e); } catch (_) {}
    }
  }

  function chartTypeOf(chart) {
    try {
      if (chart && chart.config && typeof chart.config.type === 'string') return chart.config.type;
      if (chart && chart.config && chart.config._config && typeof chart.config._config.type === 'string') return chart.config._config.type;
      if (chart && chart.options && typeof chart.options.type === 'string') return chart.options.type;
    } catch (e) {}
    return '';
  }

  function isCircular(chart) {
    var t = chartTypeOf(chart);
    return t === 'doughnut' || t === 'pie';
  }

  function applyExternalTooltip(chart) {
    try {
      if (!isCircular(chart)) return;
      if (!chart.options) return;
      chart.options.plugins = chart.options.plugins || {};
      var tt = chart.options.plugins.tooltip;
      if (!tt || typeof tt !== 'object') {
        tt = chart.options.plugins.tooltip = {};
      }
      tt.enabled = false;
      tt.external = externalTooltipHandler;
    } catch (e) {
      try { console && console.warn && console.warn('chqDonutTooltip apply:', e); } catch (_) {}
    }
  }

  function removeTooltipEl(chart) {
    try {
      var parent = chart && chart.canvas && chart.canvas.parentNode;
      if (!parent) return;
      var el = parent.querySelector('.chq-tooltip[data-chart-tooltip="' + chart.id + '"]');
      if (el) el.remove();
    } catch (e) {}
  }

  // Per-chart opt-in plugin. We DO NOT mutate options for charts that haven't
  // opted in — that keeps existing dashboards working untouched. A chart
  // opts in by setting either:
  //   options.plugins.tooltip.chqExternal = true
  //   options.plugins.chqDonutTooltip = true
  // or by globally enabling: window.__chqEnableDonutTooltip = true (which
  // turns on the external tooltip for every doughnut/pie chart).
  function shouldApply(chart) {
    if (!isCircular(chart)) return false;
    if (typeof window !== 'undefined' && window.__chqEnableDonutTooltip) return true;
    try {
      var p = chart.options && chart.options.plugins;
      if (!p) return false;
      if (p.chqDonutTooltip === true) return true;
      if (p.tooltip && p.tooltip.chqExternal === true) return true;
    } catch (e) {}
    return false;
  }

  var plugin = {
    id: 'chqDonutTooltip',
    beforeInit: function (chart) {
      if (shouldApply(chart)) applyExternalTooltip(chart);
    },
    afterDestroy: function (chart) { removeTooltipEl(chart); }
  };

  function tryRegisterChartPlugin() {
    if (typeof window === 'undefined') return false;
    if (typeof window.Chart === 'undefined' || !window.Chart.register) return false;
    if (window.__chqDonutTooltipRegistered) return true;
    try {
      window.Chart.register(plugin);
      window.__chqDonutTooltipRegistered = true;
      return true;
    } catch (e) {
      try { console && console.warn && console.warn('chqDonutTooltip register:', e); } catch (_) {}
      return false;
    }
  }

  if (!tryRegisterChartPlugin()) {
    if (typeof document !== 'undefined') {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', tryRegisterChartPlugin, { once: true });
      } else {
        setTimeout(tryRegisterChartPlugin, 0);
      }
      window.addEventListener('load', tryRegisterChartPlugin, { once: true });
    }
  }

  // ---- ApexCharts custom tooltip ----------------------------------------
  function apexCustom(args) {
    try {
      var seriesIndex = args.seriesIndex;
      var w = args.w || {};
      var globals = w.globals || {};
      var seriesArr = args.series || globals.series || [];
      var idx = seriesIndex;
      var val = Number(seriesArr[idx] || 0);
      var total = 0;
      for (var i = 0; i < seriesArr.length; i++) total += Number(seriesArr[i] || 0);
      var pct = total ? (val / total) * 100 : 0;
      var colors = globals.colors || [];
      var color = colors[idx] || '#38bdf8';
      var labels = globals.labels || globals.seriesNames || [];
      var label = labels[idx] != null ? labels[idx] : '';
      var unit = (args.unit) || '';
      var valueText = unit ? (fmtNumber(val) + ' ' + unit) : fmtNumber(val);

      return '<div class="chq-tooltip chq-tt-apex chq-tt-show">' +
        '<div class="chq-tt-row">' +
          '<span class="chq-tt-dot" style="background:' + escapeHtml(color) + '"></span>' +
          '<span class="chq-tt-label">' + escapeHtml(label) + '</span>' +
        '</div>' +
        '<div class="chq-tt-value">' + escapeHtml(valueText) + '</div>' +
        '<div class="chq-tt-pct">Ulushi: <strong>' + pct.toFixed(1) + '%</strong></div>' +
      '</div>';
    } catch (e) {
      return '';
    }
  }

  // Convenience: enable external tooltip globally for all doughnut/pie charts
  // created from this point on. Pages call `ChaqmoqDonutTooltip.enableAll()`
  // before they instantiate their charts (or at any time, before render).
  function enableAll() {
    if (typeof window === 'undefined') return;
    window.__chqEnableDonutTooltip = true;
    tryRegisterChartPlugin();
  }

  function disableAll() {
    if (typeof window === 'undefined') return;
    window.__chqEnableDonutTooltip = false;
  }

  window.ChaqmoqDonutTooltip = {
    external: externalTooltipHandler,
    apexCustom: apexCustom,
    formatNumber: fmtNumber,
    enableAll: enableAll,
    disableAll: disableAll
  };
})();
