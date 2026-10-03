/* Paper-to-Playground app runtime. Generic; reads the spec embedded in the page and
   the generated compute/render/checks functions. */
(function () {
  'use strict';
  var SPEC = JSON.parse(document.getElementById('pg-spec').textContent);
  var fmt = PG.fmt, lite = PG.lite;
  var $ = function (id) { return document.getElementById(id); };
  function h(tag, attrs, parent, html) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, String(attrs[k]));
    if (html !== undefined) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  }
  function clone(v) { return v === undefined ? v : JSON.parse(JSON.stringify(v)); }
  var CONTROLS = SPEC.controls || [];
  function defaults() { var d = {}; CONTROLS.forEach(function (c) { d[c.id] = clone(c.value); }); return d; }
  function merged(over) { var d = defaults(); if (over) for (var k in over) if (k in d) d[k] = clone(over[k]); return d; }
  var state = defaults();
  var hasCompute = function () { return typeof compute === 'function'; };

  /* ---------- static text ---------- */
  function paras(t) { if (!t) return ''; return String(t).split(/\n\s*\n/).map(function (p) { return '<p>' + lite(p) + '</p>'; }).join(''); }
  function fillText() {
    document.title = PG.lite(SPEC.title || 'Interactive explanation').replace(/<[^>]*>/g, '');
    $('pg-title').innerHTML = lite(SPEC.title);
    $('pg-tagline').innerHTML = lite(SPEC.tagline || '');
    var src = SPEC.source || {}, sl = $('pg-source'), bits = [];
    if (src.paper) bits.push('<cite>' + lite(src.paper) + '</cite>');
    if (src.authors) bits.push(lite(src.authors));
    if (src.section) bits.push(lite(src.section));
    if (src.equation) bits.push(lite(src.equation));
    sl.innerHTML = 'Source: ' + bits.join(', ');
    if (src.url && /^https?:\/\//.test(src.url)) {
      sl.appendChild(document.createTextNode(' ('));
      h('a', { href: src.url, rel: 'noopener' }, sl, 'paper link');
      sl.appendChild(document.createTextNode(')'));
    }
    $('pg-idea').innerHTML = paras(SPEC.idea);
    $('pg-why').innerHTML = paras(SPEC.why);
    if (SPEC.formula) $('pg-formula').innerHTML = lite(SPEC.formula); else $('pg-formula').style.display = 'none';
    var tb = $('pg-symbols');
    (SPEC.symbols || []).forEach(function (s) { var tr = h('tr', {}, tb); h('th', { scope: 'row' }, tr, lite(s.symbol)); h('td', {}, tr, lite(s.meaning)); });
    if (!(SPEC.symbols || []).length) $('pg-symbols-wrap').style.display = 'none';
    $('pg-figcap').innerHTML = lite(SPEC.figure_caption || '');
    var ex = $('pg-explore');
    (SPEC.explorations || []).forEach(function (e, i) {
      var art = h('article', { 'class': 'pg-exp' }, ex);
      h('h3', {}, art, 'Experiment ' + (i + 1) + ': ' + lite(e.title));
      var dl = h('dl', {}, art);
      var er = null;  // numbers quoted in the text are computed live at this experiment's preset
      try { if (hasCompute()) er = compute(clone(merged(e.preset))); } catch (x) { er = null; }
      // a placeholder that cannot be filled shows a dash, never raw {r.key} text
      var live = function (t) { return String(er ? PG.fill(t, er).text : t).replace(/\{r\.[^{}]*\}/g, '—'); };
      // predict first, then load the setup, then compare with what happens
      if (e.predict) { art.insertBefore(h('p', { 'class': 'pg-predict' }, null, '<b>Predict first:</b> ' + lite(e.predict)), dl); }
      if (e.preset && typeof e.preset === 'object' && Object.keys(e.preset).length) {
        var b = h('button', { type: 'button', 'class': 'pg-btn' }, null, 'Load this setup');
        art.insertBefore(b, dl);
        b.addEventListener('click', function () { state = merged(e.preset); buildControls(); update(); flash(); });
      }
      h('dt', {}, dl, 'Change'); h('dd', {}, dl, lite(live(e.change)));
      h('dt', {}, dl, 'Observe'); h('dd', {}, dl, lite(live(e.observe)));
      h('dt', {}, dl, 'Why'); h('dd', {}, dl, lite(live(e.why)));
    });
    var lim = SPEC.limitation || {};
    $('pg-limit-kind').innerHTML = lite(lim.kind || 'Limitation');
    $('pg-limit').innerHTML = paras(lim.text);
    var gr = SPEC.grounding || {};
    var fp = $('pg-from-paper');
    (gr.from_paper || []).forEach(function (g) {
      if (typeof g === 'string') { h('li', {}, fp, lite(g)); return; }
      h('li', {}, fp, lite(g.claim) + (g.where ? ' <span class="pg-where">(' + lite(g.where) + ')</span>' : ''));
    });
    var ours = $('pg-ours');
    (gr.ours || []).forEach(function (g) { h('li', {}, ours, lite(typeof g === 'string' ? g : g.claim)); });
  }
  function flash() {
    var b = $('pg-bench'); b.classList.remove('pg-flash'); void b.offsetWidth; b.classList.add('pg-flash');
    if (window.matchMedia && window.matchMedia('(max-width: 960px)').matches) b.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* ---------- controls ---------- */
  function plainText(s) { return String(s || '').replace(/<[^>]*>/g, ''); }
  function clamp(v, c) { if (typeof c.min === 'number') v = Math.max(c.min, v); if (typeof c.max === 'number') v = Math.min(c.max, v); return v; }
  function numIn(val, c, onset, label) {
    var i = h('input', { type: 'number', value: val, step: c.step || 'any', 'aria-label': label, inputmode: 'decimal' });
    if (typeof c.min === 'number') i.min = c.min;
    if (typeof c.max === 'number') i.max = c.max;
    i.addEventListener('input', function () { var v = parseFloat(i.value); if (isFinite(v)) { onset(clamp(v, c)); update(); } });
    i.addEventListener('change', function () { var v = parseFloat(i.value); i.value = isFinite(v) ? clamp(v, c) : val; });
    return i;
  }
  // step-through for iterative processes: a slider marked "play" can be advanced one step at a time or animated
  var playTimer = null;
  function stopPlay() { if (playTimer) { clearInterval(playTimer); playTimer = null; } }
  function playButtons(wrap, c, r, out, unit) {
    var bar = h('div', { 'class': 'pg-resize' }, wrap), st = c.step || (c.max - c.min) / 20;
    var play = h('button', { type: 'button', 'class': 'pg-btn pg-btn-small' }, bar, 'Play');
    var step = h('button', { type: 'button', 'class': 'pg-btn pg-btn-small' }, bar, 'Step');
    var reset = h('button', { type: 'button', 'class': 'pg-btn pg-btn-small' }, bar, 'Reset');
    function set(v) { state[c.id] = Math.min(c.max, Math.max(c.min, +(+v).toPrecision(12))); r.value = state[c.id]; out.innerHTML = fmt(state[c.id]) + unit; update(); }
    function advance() { if (state[c.id] + st > c.max + 1e-9) { stopPlay(); play.textContent = 'Play'; return; } set(state[c.id] + st); }
    play.addEventListener('click', function () {
      if (playTimer) { stopPlay(); play.textContent = 'Play'; return; }
      if (state[c.id] + st > c.max + 1e-9) set(c.min);
      play.textContent = 'Pause'; playTimer = setInterval(advance, 450);
    });
    step.addEventListener('click', function () { stopPlay(); play.textContent = 'Play'; advance(); });
    reset.addEventListener('click', function () { stopPlay(); play.textContent = 'Play'; set(c.min); });
  }
  function buildControls() {
    stopPlay();
    var box = $('pg-controls'); box.innerHTML = '';
    CONTROLS.forEach(function (c) {
      var wrap = h('div', { 'class': 'pg-ctl pg-ctl-' + c.type }, box), id = 'ctl-' + c.id;
      var lab = h('label', { 'for': id, 'class': 'pg-ctl-label' }, wrap, '<span>' + lite(c.label) + '</span>');
      if (c.type === 'slider') {
        var unit = c.unit ? ' ' + lite(c.unit) : '';
        var out = h('output', { 'for': id, 'class': 'pg-ctl-val' }, lab, fmt(state[c.id]) + unit);
        // a default that is not on the step grid would be silently snapped by the browser: use a continuous step then
        var st = c.step, k = st ? (state[c.id] - c.min) / st : 0;
        if (!st || Math.abs(k - Math.round(k)) > 1e-6) st = 'any';
        var r = h('input', { type: 'range', id: id, min: c.min, max: c.max, step: st, value: state[c.id] }, wrap);
        r.addEventListener('input', function () { state[c.id] = parseFloat(r.value); out.innerHTML = fmt(state[c.id]) + unit; update(); });
        if (c.play) playButtons(wrap, c, r, out, unit);
      } else if (c.type === 'number') {
        var n = numIn(state[c.id], c, function (v) { state[c.id] = v; }, plainText(c.label)); n.id = id; wrap.appendChild(n);
      } else if (c.type === 'toggle') {
        wrap.classList.add('pg-ctl-row');
        var cb = h('input', { type: 'checkbox', id: id }, null); cb.checked = !!state[c.id];
        wrap.insertBefore(cb, lab);
        cb.addEventListener('change', function () { state[c.id] = cb.checked; update(); });
      } else if (c.type === 'select') {
        var sel = h('select', { id: id }, wrap);
        (c.options || []).forEach(function (o) {
          var op = h('option', { value: JSON.stringify(o.value) }, sel, lite(o.label !== undefined ? o.label : String(o.value)));
          if (JSON.stringify(o.value) === JSON.stringify(state[c.id])) op.selected = true;
        });
        sel.addEventListener('change', function () { state[c.id] = JSON.parse(sel.value); update(); });
      } else if (c.type === 'vector' && Array.isArray(state[c.id])) {
        vectorCtl(wrap, c, id);
      } else if (c.type === 'matrix' && Array.isArray(state[c.id])) {
        matrixCtl(wrap, c, id);
      }
      if (c.help) h('div', { 'class': 'pg-help' }, wrap, lite(c.help));
    });
  }
  function vectorCtl(wrap, c, id) {
    var row = h('div', { 'class': 'pg-vec', id: id, role: 'group' }, wrap), v = state[c.id];
    v.forEach(function (x, i) {
      var cell = h('div', { 'class': 'pg-vec-cell' }, row);
      var lb = c.labels && c.labels[i] !== undefined ? c.labels[i] : String(i + 1);
      h('span', { 'class': 'pg-vec-lab' }, cell, lite(lb));
      cell.appendChild(numIn(x, c, function (val) { state[c.id][i] = val; }, plainText(c.label) + ' ' + plainText(lb)));
    });
    var rz = c.resizable;
    if (rz) {
      var bar = h('div', { 'class': 'pg-resize' }, wrap);
      var minus = h('button', { type: 'button', 'class': 'pg-btn pg-btn-small' }, bar, 'Remove last entry');
      var plus = h('button', { type: 'button', 'class': 'pg-btn pg-btn-small' }, bar, 'Add an entry');
      minus.disabled = v.length <= (rz.min || 1);
      plus.disabled = v.length >= (rz.max || 12);
      minus.addEventListener('click', function () { if (state[c.id].length > (rz.min || 1)) { state[c.id].pop(); buildControls(); update(); } });
      plus.addEventListener('click', function () { if (state[c.id].length < (rz.max || 12)) { state[c.id].push(typeof rz.fill === 'number' ? rz.fill : 0); buildControls(); update(); } });
    }
  }
  function matrixCtl(wrap, c, id) {
    var sc = h('div', { 'class': 'pg-scroll' }, wrap), t = h('table', { 'class': 'pg-mat', id: id }, sc), m = state[c.id];
    if (c.colLabels) { var hr = h('tr', {}, h('thead', {}, t)); h('th', {}, hr, ''); c.colLabels.forEach(function (l) { h('th', { scope: 'col' }, hr, lite(l)); }); }
    var tb = h('tbody', {}, t);
    m.forEach(function (row, i) {
      var tr = h('tr', {}, tb);
      h('th', { scope: 'row' }, tr, lite(c.rowLabels && c.rowLabels[i] !== undefined ? c.rowLabels[i] : 'row ' + (i + 1)));
      row.forEach(function (x, j) { var td = h('td', {}, tr); td.appendChild(numIn(x, c, function (val) { state[c.id][i][j] = val; }, plainText(c.label) + ' row ' + (i + 1) + ' column ' + (j + 1))); });
    });
  }

  /* ---------- readouts ---------- */
  var prevR = null;  // readouts from before the latest change
  function differs(a, b) { return typeof a === 'number' && typeof b === 'number' && isFinite(a) && isFinite(b) && Math.abs(a - b) > 1e-12 * Math.max(1, Math.abs(a), Math.abs(b)); }
  function readouts(r) {
    var box = $('pg-readouts'); box.innerHTML = '';
    var pr = prevR; prevR = r ? clone(r) : null;
    (SPEC.readouts || []).forEach(function (ro) {
      var v = r ? r[ro.key] : undefined, d = h('div', { 'class': 'pg-ro' }, box);
      h('div', { 'class': 'pg-ro-label' }, d, lite(ro.label));
      var val = h('div', { 'class': 'pg-ro-val' }, d), digits = typeof ro.digits === 'number' ? ro.digits : undefined;
      if (Array.isArray(v) && Array.isArray(v[0])) {
        var t = h('table', { 'class': 'pg-mini' }, h('div', { 'class': 'pg-scroll' }, val));
        var pm = pr && Array.isArray(pr[ro.key]) ? pr[ro.key] : null;
        v.forEach(function (row, i) { var tr = h('tr', {}, t); row.forEach(function (x, j) { h('td', pm && pm[i] && differs(x, pm[i][j]) ? { 'class': 'pg-chg', title: 'was ' + fmt(pm[i][j], digits) } : {}, tr, lite(fmt(x, digits))); }); });
        d.classList.add('pg-ro-wide');
      } else if (Array.isArray(v)) {
        var pa = pr && Array.isArray(pr[ro.key]) ? pr[ro.key] : null;
        val.innerHTML = '[ ' + v.map(function (x, i) { var c = pa && differs(x, pa[i]); return (c ? '<span class="pg-chg" title="was ' + fmt(pa[i], digits) + '">' : '') + lite(fmt(x, digits)) + (c ? '</span>' : ''); }).join(', ') + ' ]';
        if (v.length > 4) d.classList.add('pg-ro-wide');
      } else {
        val.innerHTML = lite(fmt(v, digits)) + (ro.unit ? ' <span class="pg-unit">' + lite(ro.unit) + '</span>' : '');
        var pv = pr ? pr[ro.key] : undefined;
        if (differs(v, pv)) val.innerHTML += ' <span class="pg-was"><span class="' + (v > pv ? 'pg-up">▲' : 'pg-down">▼') + '</span> was ' + lite(fmt(pv, digits)) + '</span>';
      }
    });
    if (r && typeof r.note === 'string' && r.note) { var n = h('div', { 'class': 'pg-ro pg-ro-wide pg-ro-note' }, box); n.innerHTML = lite(r.note); }
  }

  /* ---------- update loop ---------- */
  function errBox(msg) { var p = h('p', { 'class': 'pg-error' }, $('pg-figure')); p.textContent = msg; }
  function update() {
    var f = $('pg-figure'); f.innerHTML = '';
    if ($('pg-worked')) $('pg-worked').innerHTML = '';
    if (!hasCompute()) { errBox('The interactive model is unavailable for this page.'); readouts(null); return; }
    var r = null;
    try { r = compute(clone(state)); }
    catch (e) { errBox('The calculation could not run for these inputs: ' + e.message); readouts(null); return; }
    readouts(r);
    // the key equation with the current numbers plugged in, refreshed on every change
    var wk = $('pg-worked');
    if (wk) {
      var wf = SPEC.worked ? PG.fill(SPEC.worked, r) : null;
      wk.innerHTML = wf && !wf.bad.length ? '<span class="pg-worked-lab">With your current inputs</span>' + lite(wf.text) : '';
    }
    try { render(PG.makeV(f, { ghost: true }), clone(state), r); }
    catch (e) { errBox('The figure could not be drawn for these inputs: ' + e.message); }
  }

  /* ---------- live checks ---------- */
  function runChecks() {
    var hidden = SPEC.hidden_checks || [];
    var ul = $('pg-checks'), list = ((typeof checks !== 'undefined' && Array.isArray(checks)) ? checks : []).filter(function (c) { return hidden.indexOf(c.name) < 0; }), pass = 0;
    list.forEach(function (c) {
      var ok = false, detail = '';
      try {
        var p = merged(c.inputs), r = compute(clone(p)), res = c.test(r, p);
        if (res && typeof res === 'object') { ok = !!res.pass; detail = res.detail || ''; } else ok = !!res;
      } catch (e) { ok = false; detail = e.message; }
      if (ok) pass++;
      h('li', { 'class': ok ? 'pg-ok' : 'pg-fail' }, ul, (ok ? 'Passed: ' : 'Failed: ') + lite(c.name) + (detail ? ' <span class="pg-where">' + lite(detail) + '</span>' : ''));
    });
    $('pg-checks-sum').textContent = list.length ? (pass + ' of ' + list.length + ' checks pass, computed in your browser when the page loaded.') : 'No automatic checks are available for this page.';
  }

  // a malformed text field must not take the controls and figure down with it
  try { fillText(); } catch (e) { if (window.console) console.warn('text section failed: ' + e.message); }
  buildControls();
  $('pg-reset').addEventListener('click', function () { state = defaults(); buildControls(); update(); });
  update();
  runChecks();
})();
