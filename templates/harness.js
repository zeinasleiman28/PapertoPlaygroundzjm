/* Offline checker. Loaded before pg_v.js and the generated code inside a bare V8 context. */
var __issues = [];
function __El(tag) { this.tagName = tag; this.attrs = {}; this.children = []; this.textContent = ''; this._html = ''; }
__El.prototype.setAttribute = function (k, v) {
  v = String(v);
  if (/NaN|Infinity|undefined/.test(v) && k !== 'aria-label') __issues.push('figure attribute ' + k + '="' + v.slice(0, 60) + '" on <' + this.tagName + '>');
  this.attrs[k] = v;
};
__El.prototype.appendChild = function (c) { this.children.push(c); return c; };
Object.defineProperty(__El.prototype, 'innerHTML', { get: function () { return this._html; }, set: function (v) { this._html = String(v); } });
var document = { createElement: function (t) { return new __El(t); }, createElementNS: function (ns, t) { return new __El(t); } };
var window = undefined, fetch = undefined, XMLHttpRequest = undefined;

function __walk(n, acc) {
  acc.nodes++;
  var t = (n.textContent || '') + ' ' + (n._html || '');
  // a value printed as NaN/undefined is a bug; the word in prose ("PPV is undefined here") is not
  // value-like "= undefined", ": undefined" or a bare "undefined" label; prose such as "PPV is undefined here" is fine
  var m = /\bNaN\b|\[object Object\]|(?:[=:(\[,]\s*|^\s*)undefined\b/m.exec(t);
  if (m) acc.bad.push('...' + t.slice(Math.max(0, m.index - 70), m.index + 30).trim() + '...');  // context around the bad token
  for (var i = 0; i < n.children.length; i++) __walk(n.children[i], acc);
  return acc;
}
function __clone(v) { return JSON.parse(JSON.stringify(v)); }
function __nonFinite(v, path, out) {
  if (out.length > 4) return;
  // NaN is always a bug; +/-Infinity can be a correct value (e.g. a decay time with zero damping) and is shown as ∞.
  // Figures are still checked separately for invalid coordinates.
  if (typeof v === 'number') { if (isNaN(v)) out.push(path + '=' + v); }
  else if (Array.isArray(v)) v.forEach(function (x, i) { __nonFinite(x, path + '[' + i + ']', out); });
  else if (v && typeof v === 'object') Object.keys(v).forEach(function (k) { __nonFinite(v[k], path + '.' + k, out); });
}

function __run(spec) {
  var rep = { critical: [], major: [], minor: [], stats: {} };
  if (typeof compute !== 'function') { rep.critical.push('CODE does not define function compute(p)'); return JSON.stringify(rep); }
  if (typeof render !== 'function') { rep.critical.push('CODE does not define function render(V, p, r)'); return JSON.stringify(rep); }
  var C = spec.controls || [], d = {};
  C.forEach(function (c) { d[c.id] = __clone(c.value); });
  function merged(o) { var m = __clone(d); if (o) for (var k in o) { if (k in m) m[k] = __clone(o[k]); } return m; }

  var cases = [{ label: 'default inputs', p: merged(null), kind: 'default' }];
  (spec.explorations || []).forEach(function (e, i) { cases.push({ label: 'experiment ' + (i + 1) + ' preset', p: merged(e.preset), kind: 'preset' }); });
  C.forEach(function (c) {
    function add(v, what) { var o = {}; o[c.id] = v; cases.push({ label: 'control "' + c.id + '" ' + what, p: merged(o), kind: 'edge' }); }
    if (c.type === 'slider' || c.type === 'number') {
      if (typeof c.min === 'number') add(c.min, 'at min ' + c.min);
      if (typeof c.max === 'number') add(c.max, 'at max ' + c.max);
    } else if (c.type === 'toggle') add(!c.value, 'flipped');
    else if (c.type === 'select') (c.options || []).forEach(function (o) { add(o.value, '= ' + JSON.stringify(o.value)); });
    else if (c.type === 'vector' && Array.isArray(c.value)) {
      var n = c.value.length, lo = typeof c.min === 'number' ? c.min : 0;
      var z = []; for (var i = 0; i < n; i++) z.push(Math.max(lo, 0)); add(z, 'all ' + Math.max(lo, 0));
      var eq = []; for (i = 0; i < n; i++) eq.push(Math.max(lo, 1)); add(eq, 'all equal');
      var oh = []; for (i = 0; i < n; i++) oh.push(i === 0 ? (typeof c.max === 'number' ? c.max : 5) : Math.max(lo, 0)); add(oh, 'one large entry');
      if (c.resizable) {
        var f = typeof c.resizable.fill === 'number' ? c.resizable.fill : 0;
        var mn = c.value.slice(0, c.resizable.min || 1); add(mn, 'shortest length');
        var mx = c.value.slice(); while (mx.length < (c.resizable.max || n)) mx.push(f); add(mx, 'longest length');
      }
    } else if (c.type === 'matrix' && Array.isArray(c.value)) {
      add(c.value.map(function (r) { return r.map(function () { return 0; }); }), 'all zeros');
      add(c.value.map(function (r) { return r.map(function () { return 1; }); }), 'all ones');
    }
  });

  // combined extremes catch 0/0 cases that single-control edges miss (e.g. two probabilities at 0 and 1)
  [['min', 'max'], ['max', 'min'], ['min', 'min'], ['max', 'max']].forEach(function (pair, k) {
    var ep = merged(null), any = false;
    C.forEach(function (c, i) {
      if (c.type === 'slider' && typeof c.min === 'number' && typeof c.max === 'number') { ep[c.id] = c[pair[i % 2]]; any = true; }
      // vectors and matrices go to all zeros (or their minimum if zero is not allowed) at the same time
      var z = typeof c.min === 'number' && c.min > 0 ? c.min : 0;
      if (c.type === 'vector' && Array.isArray(ep[c.id])) { ep[c.id] = ep[c.id].map(function () { return z; }); any = true; }
      if (c.type === 'matrix' && Array.isArray(ep[c.id])) { ep[c.id] = ep[c.id].map(function (r) { return r.map(function () { return z; }); }); any = true; }
    });
    if (any) cases.push({ label: 'combined extremes (sliders ' + pair.join('/') + ' alternating, vectors/matrices zero) ' + JSON.stringify(ep).slice(0, 120), p: ep, kind: 'edge' });
  });
  var seed = 12345; function rnd() { seed = (1664525 * seed + 1013904223) >>> 0; return seed / 4294967296; }
  for (var k = 0; k < 4; k++) {
    var rp = merged(null);
    C.forEach(function (c) {
      var lo = typeof c.min === 'number' ? c.min : 0, hi = typeof c.max === 'number' ? c.max : (lo + 1), st = c.step || 0;
      function rv() { var v = lo + rnd() * (hi - lo); return st ? Math.min(hi, Math.max(lo, Math.round(v / st) * st)) : v; }
      if (c.type === 'slider') rp[c.id] = rv();
      else if (c.type === 'toggle') rp[c.id] = rnd() < 0.5;
      else if (c.type === 'select' && (c.options || []).length) rp[c.id] = c.options[Math.floor(rnd() * c.options.length)].value;
      else if (c.type === 'vector' && Array.isArray(rp[c.id])) rp[c.id] = rp[c.id].map(rv);
      else if (c.type === 'matrix' && Array.isArray(rp[c.id])) rp[c.id] = rp[c.id].map(function (r) { return r.map(rv); });
    });
    cases.push({ label: 'random inputs #' + (k + 1) + ' ' + JSON.stringify(rp).slice(0, 120), p: rp, kind: 'edge' });
  }

  // numbers in exploration text must come from compute() through {r.key} placeholders that resolve at the preset
  rep.stats.live_numbers = 0;
  (spec.explorations || []).forEach(function (e, i) {
    var r; try { r = compute(merged(e.preset)); } catch (x) { return; }
    ['change', 'observe', 'why'].forEach(function (k) {
      var f = PG.fill(e[k], r);
      rep.stats.live_numbers += ((String(e[k] || '').match(/\{r\./g)) || []).length - f.bad.length;
      if (f.bad.length) rep.major.push('exploration ' + (i + 1) + ' ' + k + ': placeholder ' + f.bad.join(', ') + ' does not resolve to a value in compute() output at its preset; available keys: ' + Object.keys(r).join(', '));
    });
  });

  var defaultPanels = 0;
  cases.forEach(function (cs) {
    var bucket = cs.kind === 'edge' ? rep.major : rep.critical;
    var r;
    try { r = compute(__clone(cs.p)); }
    catch (e) { (cs.kind === 'default' ? rep.critical : bucket).push('compute() threw on ' + cs.label + ': ' + e.message); return; }
    if (!r || typeof r !== 'object') { bucket.push('compute() must return an object (' + cs.label + ')'); return; }
    var nf = []; __nonFinite(r, 'r', nf);
    if (nf.length) rep.major.push('compute() returned NaN on ' + cs.label + ': ' + nf.join(', '));
    if (cs.kind === 'default') {
      rep.missing_readouts = [];
      (spec.readouts || []).forEach(function (ro) { if (!(ro.key in r)) { rep.missing_readouts.push(ro.key); rep.major.push('readout key "' + ro.key + '" is not returned by compute()'); } });
    }
    __issues = [];
    var root = new __El('div');
    try { render(PG.makeV(root), __clone(cs.p), r); }
    catch (e) { (cs.kind === 'default' ? rep.critical : rep.major).push('render() threw on ' + cs.label + ': ' + e.message); return; }
    var acc = __walk(root, { nodes: 0, bad: [] });
    if (cs.kind === 'default') { defaultPanels = root.children.length; rep.stats.figure_nodes = acc.nodes; }
    if (__issues.length) rep.major.push('figure has invalid coordinates on ' + cs.label + ': ' + __issues.slice(0, 2).join('; '));
    if (acc.bad.length) rep.major.push('figure text shows NaN/undefined on ' + cs.label + ': "' + acc.bad[0] + '"');
  });
  if (defaultPanels < 1) rep.critical.push('render() drew nothing with default inputs');
  rep.stats.panels = defaultPanels;
  rep.stats.cases = cases.length;

  // every control must change compute() output (a control that does nothing is not a meaningful control)
  function __ser(n) { return n.tagName + JSON.stringify(n.attrs) + n.textContent + n._html + '[' + n.children.map(__ser).join(',') + ']'; }
  function __sig(p) { var r = compute(__clone(p)), root = new __El('div'); try { render(PG.makeV(root), __clone(p), r); } catch (e) {} return JSON.stringify(r) + __ser(root); }
  // a control is dead only if it has no effect from EVERY starting state (default, presets, random states)
  var bases = cases.filter(function (cs) { return cs.kind !== 'edge' || /^random/.test(cs.label); }).map(function (cs) { return cs.p; });
  C.forEach(function (c) {
    var moved = bases.some(function (b) {
      var v = b[c.id], cands = [], sb;
      try { sb = __sig(b); } catch (e) { return false; }
      if (c.type === 'slider' || c.type === 'number') cands = [c.min, c.max, typeof v === 'number' ? v + (c.step || 1) : undefined];
      else if (c.type === 'toggle') cands = [!v];
      else if (c.type === 'select') cands = (c.options || []).map(function (o) { return o.value; });
      else if (c.type === 'vector' && Array.isArray(v)) cands = [v.map(function (x, i) { return i === 0 ? x + 1 : x; }), v.map(function (x, i) { return i === v.length - 1 ? x - 1 : x; })];
      else if (c.type === 'matrix' && Array.isArray(v)) cands = [v.map(function (r, i) { return r.map(function (x, j) { return i === 0 && j === 0 ? x + 1 : x; }); })];
      return cands.some(function (x) {
        if (x === undefined || JSON.stringify(x) === JSON.stringify(v)) return false;
        var n = __clone(b); n[c.id] = __clone(x);
        try { return __sig(n) !== sb; } catch (e) { return true; }
      });
    });
    if (!moved) rep.major.push('control "' + c.id + '" has no effect: changing it changes neither compute() output nor the figure');
  });

  var list = (typeof checks !== 'undefined' && Array.isArray(checks)) ? checks : null;
  if (!list) rep.major.push('CODE does not define const checks = [...]');
  else {
    if (list.length < 2) rep.minor.push('fewer than 2 checks defined');
    var passed = 0, results = [];
    list.forEach(function (c, i) {
      var ok = false, detail = '';
      var r;
      try {
        var p = merged(c.inputs); r = compute(__clone(p)); var res = c.test(r, p);
        if (res && typeof res === 'object') { ok = !!res.pass; detail = res.detail || ''; } else ok = !!res;
      } catch (e) { detail = 'threw: ' + e.message; }
      if (ok) passed++; else rep.major.push('check "' + (c.name || i) + '" fails' + (detail ? ' (' + detail + ')' : '') + '; compute() returned ' + (r ? JSON.stringify(r).slice(0, 260) : 'nothing') + '. Recompute the expected value by hand: fix compute() if the check is right, otherwise fix the check.');
      results.push({ name: c.name, pass: ok });
    });
    rep.stats.checks_passed = passed; rep.stats.checks_total = list.length; rep.stats.check_results = results;
  }
  return JSON.stringify(rep);
}
