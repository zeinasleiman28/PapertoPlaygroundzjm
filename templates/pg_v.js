/* Paper-to-Playground visual library. Generic: contains no paper-specific content.
   Exposes PG.fmt, PG.lite, PG.makeV(container). Depends only on a minimal DOM. */
var PG = (function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';

  function fmt(x, d) {
    if (x === null || x === undefined) return '\u2014';
    if (typeof x === 'boolean') return x ? 'true' : 'false';
    if (typeof x !== 'number') return String(x);
    if (!isFinite(x)) return isNaN(x) ? 'NaN' : (x > 0 ? '\u221e' : '\u2212\u221e');
    if (typeof d === 'number') return x.toFixed(d);
    var a = Math.abs(x);
    if (a === 0) return '0';
    if (a >= 1e5 || a < 1e-3) return x.toExponential(2);
    return String(+x.toPrecision(4));
  }

  // Minimal safe HTML: escape tags, then re-allow a few inline ones.
  function lite(s) {
    if (s === null || s === undefined) return '';
    s = String(s).replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return s.replace(/&lt;(\/?)(sub|sup|b|i|em|strong|code|br|small)\s*\/?&gt;/g, '<$1$2>');
  }
  function plain(s) { return String(s === undefined || s === null ? '' : s).replace(/<[^>]*>/g, ''); }

  function h(tag, attrs, parent, svg) {
    var e = svg ? document.createElementNS(NS, tag) : document.createElement(tag);
    if (attrs) for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, String(attrs[k]));
    if (parent) parent.appendChild(e);
    return e;
  }
  function s(tag, attrs, parent) { return h(tag, attrs, parent, true); }
  function r2(v) { return Math.round(v * 100) / 100; }
  function txt(parent, x, y, str, cls, anchor, extra) {
    var a = { x: r2(x), y: r2(y), 'class': cls || 'pg-t', 'text-anchor': anchor || 'middle' };
    if (extra) for (var k in extra) a[k] = extra[k];
    var t = s('text', a, parent);
    t.textContent = plain(str);
    return t;
  }

  function need(cond, msg) { if (!cond) throw new Error(msg); }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function numArr(a, name) {
    need(Array.isArray(a), name + ' must be an array');
    for (var i = 0; i < a.length; i++) need(isNum(a[i]), name + '[' + i + '] is not a finite number (' + a[i] + ')');
    return a;
  }

  function niceStep(span, n) {
    var raw = span / Math.max(1, n), p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p;
    return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p;
  }
  function ticks(lo, hi, n) {
    if (hi - lo < 1e-12) { hi = lo + 1; }
    var st = niceStep(hi - lo, n || 5), out = [];
    for (var v = Math.ceil(lo / st - 1e-9) * st; v <= hi + st * 1e-9; v += st) out.push(Math.abs(v) < st * 1e-9 ? 0 : +v.toPrecision(12));
    return out;
  }
  function range(vals, lo, hi, includeZero) {
    var mn = Infinity, mx = -Infinity;
    for (var i = 0; i < vals.length; i++) { if (vals[i] < mn) mn = vals[i]; if (vals[i] > mx) mx = vals[i]; }
    if (!isFinite(mn)) { mn = 0; mx = 1; }
    if (includeZero) { mn = Math.min(mn, 0); mx = Math.max(mx, 0); }
    if (isNum(lo)) mn = lo;
    if (isNum(hi)) mx = hi;
    if (mx - mn < 1e-12) { var pad = Math.abs(mx) > 0 ? Math.abs(mx) * 0.5 : 1; mx += pad; if (!includeZero) mn -= pad; }
    return [mn, mx];
  }
  var TONES = { accent: 1, alt: 1, warn: 1, muted: 1, ink: 1, ours: 1 };
  function tone(t, dflt) { return TONES[t] ? t : (dflt || 'accent'); }
  var CYCLE = ['accent', 'ours', 'alt', 'muted'];

  function makeV(container) {
    var V = {}, uid = 0;
    function panel(title) {
      var f = h('figure', { 'class': 'pg-panel' }, container);
      if (title) { var c = h('div', { 'class': 'pg-panel-title' }, f); c.innerHTML = lite(title); }
      return f;
    }
    function svgBox(parent, w, hgt, label) {
      return s('svg', { viewBox: '0 0 ' + w + ' ' + hgt, 'class': 'pg-svg', role: 'img', 'aria-label': plain(label || 'figure'), preserveAspectRatio: 'xMidYMid meet' }, parent);
    }
    function axes(g, x0, y0, x1, y1, yLo, yHi, yLabel, xLabel, d) {
      var ys = ticks(yLo, yHi, 5);
      for (var i = 0; i < ys.length; i++) {
        var yy = y1 - (ys[i] - yLo) / (yHi - yLo) * (y1 - y0);
        s('line', { x1: x0, x2: x1, y1: r2(yy), y2: r2(yy), 'class': 'pg-gridline' }, g);
        txt(g, x0 - 6, yy + 4, fmt(ys[i], d), 'pg-tick', 'end');
      }
      s('line', { x1: x0, x2: x0, y1: y0, y2: y1, 'class': 'pg-axis' }, g);
      if (yLabel) txt(g, 14, (y0 + y1) / 2, yLabel, 'pg-axlabel', 'middle', { transform: 'rotate(-90 14 ' + r2((y0 + y1) / 2) + ')' });
      if (xLabel) txt(g, (x0 + x1) / 2, y1 + 40, xLabel, 'pg-axlabel');
    }
    function legend(g, items, x, y) {
      items.forEach(function (it, k) {
        s('rect', { x: x, y: r2(y + k * 16), width: 10, height: 10, 'class': 'pg-fill-' + it.t }, g);
        txt(g, x + 15, y + k * 16 + 9, it.name, 'pg-legend', 'start');
      });
    }

    /* Bar chart. o: {title, labels, values | series:[{name, values, tone}], highlight, yLabel, xLabel, min, max, digits, refLines:[{y,label}], showValues} */
    V.bars = function (o) {
      need(o && Array.isArray(o.labels), 'V.bars: labels array required');
      var series = o.series || [{ name: o.name || '', values: o.values, tone: o.tone }];
      need(series.length >= 1, 'V.bars: values or series required');
      var all = [];
      series.forEach(function (sr, k) {
        numArr(sr.values, 'V.bars series ' + k + ' values');
        need(sr.values.length === o.labels.length, 'V.bars: labels length ' + o.labels.length + ' != values length ' + sr.values.length);
        all = all.concat(sr.values);
      });
      (o.refLines || []).forEach(function (r) { need(isNum(r.y), 'V.bars: refLine y must be finite'); all.push(r.y); });
      var rg = range(all, o.min, o.max, true), lo = rg[0], hi = rg[1];
      var W = 640, H = 300, ml = 58, mr = 14, mt = 18, mb = o.xLabel ? 58 : 40;
      var f = panel(o.title), svg = svgBox(f, W, H, o.title), g = s('g', {}, svg);
      var x0 = ml, x1 = W - mr, y0 = mt, y1 = H - mb;
      axes(g, x0, y0, x1, y1, lo, hi, o.yLabel, o.xLabel);
      var Y = function (v) { return y1 - (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo) * (y1 - y0); };
      s('line', { x1: x0, x2: x1, y1: r2(Y(0)), y2: r2(Y(0)), 'class': 'pg-axis' }, g);
      var n = o.labels.length, gw = (x1 - x0) / Math.max(1, n), bw = Math.min(70, gw * 0.72 / series.length);
      var hl = o.highlight === undefined || o.highlight === null ? [] : [].concat(o.highlight);
      for (var i = 0; i < n; i++) {
        var cx = x0 + gw * (i + 0.5);
        series.forEach(function (sr, k) {
          var v = sr.values[i], bx = cx - bw * series.length / 2 + bw * k;
          var top = Math.min(Y(v), Y(0)), hh = Math.max(0.5, Math.abs(Y(v) - Y(0)));
          var t = hl.indexOf(i) >= 0 ? 'alt' : tone(sr.tone, CYCLE[k % 4]);
          s('rect', { x: r2(bx + 1), y: r2(top), width: r2(Math.max(1, bw - 2)), height: r2(hh), 'class': 'pg-fill-' + t }, g);
          if (o.showValues !== false && n * series.length <= 24) txt(g, bx + bw / 2, (v >= 0 ? top - 5 : top + hh + 13), fmt(v, o.digits), 'pg-val');
        });
        txt(g, cx, y1 + 18, o.labels[i], 'pg-tick');
      }
      (o.refLines || []).forEach(function (r) {
        s('line', { x1: x0, x2: x1, y1: r2(Y(r.y)), y2: r2(Y(r.y)), 'class': 'pg-ref' }, g);
        if (r.label) txt(g, x1 - 4, Y(r.y) - 5, r.label, 'pg-reflabel', 'end');
      });
      if (series.length > 1) legend(g, series.map(function (sr, k) { return { name: sr.name, t: tone(sr.tone, CYCLE[k % 4]) }; }), x0 + 6, y0 + 4);
      return f;
    };

    /* Line plot. o: {title, series:[{name, x, y, tone, dashed}], points:[{x,y,label,tone}], vlines:[{x,label}], hlines:[{y,label}], xLabel, yLabel, xmin, xmax, ymin, ymax, digits} */
    V.line = function (o) {
      need(o && Array.isArray(o.series) && o.series.length, 'V.line: series array required');
      var xs = [], ys = [];
      o.series.forEach(function (sr, k) {
        numArr(sr.x, 'V.line series ' + k + ' x'); numArr(sr.y, 'V.line series ' + k + ' y');
        need(sr.x.length === sr.y.length, 'V.line series ' + k + ': x and y lengths differ');
        xs = xs.concat(sr.x); ys = ys.concat(sr.y);
      });
      (o.points || []).forEach(function (p, i) { need(isNum(p.x) && isNum(p.y), 'V.line: point ' + i + ' not finite'); xs.push(p.x); ys.push(p.y); });
      (o.vlines || []).forEach(function (v) { need(isNum(v.x), 'V.line: vline x not finite'); xs.push(v.x); });
      (o.hlines || []).forEach(function (v) { need(isNum(v.y), 'V.line: hline y not finite'); ys.push(v.y); });
      // optional log axes: positions use log10; non-positive values are rejected so nothing is drawn wrongly
      var lx = !!o.xLog, ly = !!o.yLog;
      function lg(v, nm) { need(v > 0, 'V.line: ' + nm + ' must be > 0 on a log axis (got ' + v + ')'); return Math.log(v) / Math.LN10; }
      if (lx) xs = xs.map(function (v) { return lg(v, 'x'); });
      if (ly) ys = ys.map(function (v) { return lg(v, 'y'); });
      var rx = range(xs, lx && isNum(o.xmin) ? lg(o.xmin, 'xmin') : o.xmin, lx && isNum(o.xmax) ? lg(o.xmax, 'xmax') : o.xmax, false),
          ry = range(ys, ly && isNum(o.ymin) ? lg(o.ymin, 'ymin') : o.ymin, ly && isNum(o.ymax) ? lg(o.ymax, 'ymax') : o.ymax, false);
      if (lx && !isNum(o.xmin) && !isNum(o.xmax)) rx = [Math.floor(rx[0] + 1e-9), Math.ceil(rx[1] - 1e-9)];
      if (ly && !isNum(o.ymin) && !isNum(o.ymax)) ry = [Math.floor(ry[0] + 1e-9), Math.ceil(ry[1] - 1e-9)];
      if (rx[1] <= rx[0]) rx[1] = rx[0] + 1;
      if (ry[1] <= ry[0]) ry[1] = ry[0] + 1;
      var W = 640, H = 300, ml = 58, mr = 16, mt = 18, mb = o.xLabel ? 58 : 40;
      var f = panel(o.title), svg = svgBox(f, W, H, o.title), g = s('g', {}, svg);
      var x0 = ml, x1 = W - mr, y0 = mt, y1 = H - mb;
      var Xl = function (v) { return x0 + (v - rx[0]) / (rx[1] - rx[0]) * (x1 - x0); };
      var Yl = function (v) { return y1 - (v - ry[0]) / (ry[1] - ry[0]) * (y1 - y0); };
      var X = function (v) { return Xl(lx ? Math.log(v) / Math.LN10 : v); };
      var Y = function (v) { return Yl(ly ? Math.log(v) / Math.LN10 : v); };
      function logTicks(lo, hi) { var out = []; for (var e = Math.ceil(lo - 1e-9); e <= hi + 1e-9; e++) out.push(e); return out.length >= 2 ? out : ticks(lo, hi, 4); }
      if (ly) {
        logTicks(ry[0], ry[1]).forEach(function (e) { var yy = Yl(e); s('line', { x1: x0, x2: x1, y1: r2(yy), y2: r2(yy), 'class': 'pg-gridline' }, g); txt(g, x0 - 6, yy + 4, fmt(Math.pow(10, e)), 'pg-tick', 'end'); });
        s('line', { x1: x0, x2: x0, y1: y0, y2: y1, 'class': 'pg-axis' }, g);
        if (o.yLabel) txt(g, 14, (y0 + y1) / 2, o.yLabel, 'pg-axlabel', 'middle', { transform: 'rotate(-90 14 ' + r2((y0 + y1) / 2) + ')' });
        if (o.xLabel) txt(g, (x0 + x1) / 2, y1 + 40, o.xLabel, 'pg-axlabel');
      } else axes(g, x0, y0, x1, y1, ry[0], ry[1], o.yLabel, o.xLabel, o.digits);
      (lx ? logTicks(rx[0], rx[1]) : ticks(rx[0], rx[1], 6)).forEach(function (t) {
        var xx = Xl(t), anc = xx > x1 - 24 ? 'end' : (xx < x0 + 10 ? 'start' : 'middle');
        txt(g, xx, y1 + 18, fmt(lx ? Math.pow(10, t) : t), 'pg-tick', anc);
      });
      s('line', { x1: x0, x2: x1, y1: y1, y2: y1, 'class': 'pg-axis' }, g);
      var clipId = 'pgc' + Math.random().toString(36).slice(2, 8) + (++uid);
      var cp = s('clipPath', { id: clipId }, s('defs', {}, svg));
      s('rect', { x: x0, y: y0 - 2, width: x1 - x0, height: y1 - y0 + 4 }, cp);
      var pg = s('g', { 'clip-path': 'url(#' + clipId + ')' }, g);
      (o.hlines || []).forEach(function (v) { s('line', { x1: x0, x2: x1, y1: r2(Y(v.y)), y2: r2(Y(v.y)), 'class': 'pg-ref' }, pg); if (v.label) txt(g, x1 - 4, Y(v.y) - 5, v.label, 'pg-reflabel', 'end'); });
      (o.vlines || []).forEach(function (v) { s('line', { x1: r2(X(v.x)), x2: r2(X(v.x)), y1: y0, y2: y1, 'class': 'pg-ref' }, pg); if (v.label) txt(g, X(v.x) + 4, y0 + 12, v.label, 'pg-reflabel', 'start'); });
      o.series.forEach(function (sr, k) {
        var d = '';
        for (var i = 0; i < sr.x.length; i++) d += (i ? 'L' : 'M') + r2(X(sr.x[i])) + ' ' + r2(Y(sr.y[i]));
        var t = tone(sr.tone, CYCLE[k % 4]);
        if (d) s('path', { d: d, 'class': 'pg-stroke-' + t + (sr.dashed ? ' pg-dashed' : '') }, pg);
      });
      (o.points || []).forEach(function (p) {
        s('circle', { cx: r2(X(p.x)), cy: r2(Y(p.y)), r: 5, 'class': 'pg-fill-' + tone(p.tone, 'alt') + ' pg-dot' }, g);
        if (p.label) txt(g, X(p.x) + 8, Y(p.y) - 8, p.label, 'pg-val', 'start');
      });
      if (o.series.length > 1) legend(g, o.series.map(function (sr, k) { return { name: sr.name || ('series ' + (k + 1)), t: tone(sr.tone, CYCLE[k % 4]) }; }), x0 + 8, y0 + 4);
      return f;
    };

    /* Heatmap of a matrix. o: {title, matrix, rowLabels, colLabels, min, max, digits, showValues, highlight:[[r,c],...]} */
    V.heatmap = function (o) {
      need(o && Array.isArray(o.matrix) && o.matrix.length, 'V.heatmap: matrix required');
      var R = o.matrix.length, C = (o.matrix[0] || []).length, all = [];
      o.matrix.forEach(function (row, i) { numArr(row, 'V.heatmap row ' + i); need(row.length === C, 'V.heatmap: ragged matrix'); all = all.concat(row); });
      var rg = range(all, o.min, o.max, false), lo = rg[0], hi = rg[1], div = lo < 0 && hi > 0;
      var m = Math.max(Math.abs(lo), Math.abs(hi));
      var cell = Math.min(64, Math.floor(540 / Math.max(C, 1))), ml = 70, mt = 26;
      var W = ml + C * cell + 10, H = mt + R * cell + 10;
      var f = panel(o.title), svg = svgBox(f, W, H, o.title), g = s('g', {}, svg);
      var hls = (o.highlight || []).map(function (p) { return p[0] + ',' + p[1]; });
      for (var i = 0; i < R; i++) {
        txt(g, ml - 8, mt + i * cell + cell / 2 + 4, o.rowLabels && o.rowLabels[i] !== undefined ? o.rowLabels[i] : 'row ' + (i + 1), 'pg-tick', 'end');
        for (var j = 0; j < C; j++) {
          var v = o.matrix[i][j], t, a;
          if (div) { t = v < 0 ? 'ours' : 'accent'; a = Math.abs(v) / (m || 1); }
          else { t = 'accent'; a = (v - lo) / ((hi - lo) || 1); }
          a = Math.max(0.06, Math.min(1, a));
          s('rect', { x: ml + j * cell + 1, y: mt + i * cell + 1, width: cell - 2, height: cell - 2, 'class': 'pg-fill-' + t, 'fill-opacity': r2(a) }, g);
          if (hls.indexOf(i + ',' + j) >= 0) s('rect', { x: ml + j * cell + 1, y: mt + i * cell + 1, width: cell - 2, height: cell - 2, 'class': 'pg-hl' }, g);
          if (o.showValues !== false && cell >= 30) txt(g, ml + j * cell + cell / 2, mt + i * cell + cell / 2 + 4, fmt(v, o.digits), a > 0.55 ? 'pg-val pg-val-inv' : 'pg-val');
        }
      }
      for (var jj = 0; jj < C; jj++) txt(g, ml + jj * cell + cell / 2, mt - 8, o.colLabels && o.colLabels[jj] !== undefined ? o.colLabels[jj] : 'col ' + (jj + 1), 'pg-tick');
      return f;
    };

    /* Free diagram in viewBox units. */
    V.diagram = function (o) {
      need(o && Array.isArray(o.items), 'V.diagram: items array required');
      var W = o.width || 640, H = o.height || 300;
      need(isNum(W) && isNum(H), 'V.diagram: width/height must be numbers');
      var f = panel(o.title), svg = svgBox(f, W, H, o.title);
      var mid = 'pga' + Math.random().toString(36).slice(2, 8) + (++uid), defs = s('defs', {}, svg);
      ['accent', 'alt', 'warn', 'muted', 'ink', 'ours'].forEach(function (t) {
        var mk = s('marker', { id: mid + t, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' }, defs);
        s('path', { d: 'M0 0L10 5L0 10z', 'class': 'pg-fill-' + t }, mk);
      });
      var g = s('g', {}, svg);
      o.items.forEach(function (it, k) {
        need(it && typeof it === 'object', 'V.diagram item ' + k + ' must be an object');
        var t = tone(it.tone, it.type === 'text' ? 'ink' : 'accent'), nm = 'V.diagram item ' + k + ' (' + it.type + ')';
        if (it.type === 'rect') {
          numArr([it.x, it.y, it.w, it.h], nm);
          s('rect', { x: r2(it.x), y: r2(it.y), width: r2(Math.max(0, it.w)), height: r2(Math.max(0, it.h)), rx: 6, 'class': it.fill === false ? 'pg-box-' + t : 'pg-soft-' + t }, g);
          if (it.label !== undefined) txt(g, it.x + it.w / 2, it.y + it.h / 2 + (it.sub !== undefined ? -2 : 5), it.label, 'pg-dlabel');
          if (it.sub !== undefined) txt(g, it.x + it.w / 2, it.y + it.h / 2 + 15, it.sub, 'pg-dsub');
        } else if (it.type === 'circle') {
          numArr([it.cx, it.cy, it.r], nm);
          s('circle', { cx: r2(it.cx), cy: r2(it.cy), r: r2(Math.max(0, it.r)), 'class': 'pg-soft-' + t }, g);
          if (it.label !== undefined) txt(g, it.cx, it.cy + 5, it.label, 'pg-dlabel');
        } else if (it.type === 'arrow' || it.type === 'line') {
          numArr([it.x1, it.y1, it.x2, it.y2], nm);
          var a = { x1: r2(it.x1), y1: r2(it.y1), x2: r2(it.x2), y2: r2(it.y2), 'class': 'pg-stroke-' + t + (it.dashed ? ' pg-dashed' : '') };
          if (isNum(it.width)) a['stroke-width'] = r2(Math.max(0.5, Math.min(14, it.width)));
          if (it.type === 'arrow') a['marker-end'] = 'url(#' + mid + t + ')';
          s('line', a, g);
          if (it.label !== undefined) txt(g, (it.x1 + it.x2) / 2, (it.y1 + it.y2) / 2 - 7, it.label, 'pg-val');
        } else if (it.type === 'text') {
          numArr([it.x, it.y], nm);
          txt(g, it.x, it.y, it.text, 'pg-dtext pg-tone-' + t, it.anchor || 'middle', isNum(it.size) ? { 'font-size': it.size } : null);
        } else if (it.type === 'path') {
          need(typeof it.d === 'string' && !/NaN|Infinity|undefined/.test(it.d), nm + ': d must be a valid path string');
          s('path', { d: it.d, 'class': it.fill ? 'pg-soft-' + t : 'pg-stroke-' + t }, g);
        } else {
          throw new Error(nm + ': unknown item type');
        }
      });
      return f;
    };

    /* Step-by-step numeric table. o: {title, columns:[...], rows:[[...]], highlightRow, digits} */
    V.table = function (o) {
      need(o && Array.isArray(o.columns) && Array.isArray(o.rows), 'V.table: columns and rows required');
      var f = panel(o.title), wrap = h('div', { 'class': 'pg-scroll' }, f), t = h('table', { 'class': 'pg-table' }, wrap);
      var tr = h('tr', {}, h('thead', {}, t));
      o.columns.forEach(function (c) { h('th', {}, tr).innerHTML = lite(c); });
      var tb = h('tbody', {}, t);
      o.rows.forEach(function (row, i) {
        need(Array.isArray(row), 'V.table: row ' + i + ' must be an array');
        var r = h('tr', i === o.highlightRow ? { 'class': 'pg-hlrow' } : {}, tb);
        row.forEach(function (c) { var td = h('td', {}, r); if (typeof c === 'number') td.textContent = fmt(c, o.digits); else td.innerHTML = lite(c); });
      });
      return f;
    };

    /* One line of worked arithmetic or a short note. tone: accent|alt|warn|ours|ink */
    V.note = function (html, t) {
      var p = h('p', { 'class': 'pg-note pg-note-' + tone(t, 'ink') }, container);
      p.innerHTML = lite(html);
      return p;
    };

    V.fmt = fmt;
    return V;
  }

  /* Fill {r.key}, {r.key[0][1]} or {r.key:3} placeholders with live values from compute(). Returns {text, bad}. */
  function fill(text, r) {
    var bad = [];
    var out = String(text === undefined || text === null ? '' : text).replace(/\{r\.([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*|\[\d+\])*)(?::(\d))?\}/g, function (m, path, d) {
      var v = r, parts = path.match(/[A-Za-z_$][\w$]*|\d+/g);
      for (var i = 0; i < parts.length && v !== undefined && v !== null; i++) v = v[parts[i]];
      if (typeof v === 'number' && isFinite(v)) return fmt(v, d === undefined ? undefined : +d);
      if (typeof v === 'string' || typeof v === 'boolean') return String(v);
      var flat = function (x) { return Array.isArray(x) ? '[' + x.map(flat).join(', ') + ']' : (typeof x === 'number' && isFinite(x) ? fmt(x, d === undefined ? undefined : +d) : null); };
      if (Array.isArray(v) && v.length && v.length <= 12 && flat(v).indexOf('null') < 0) return flat(v);
      bad.push(m); return m;
    });
    return { text: out, bad: bad };
  }

  return { fmt: fmt, lite: lite, makeV: makeV, ticks: ticks, fill: fill };
})();
