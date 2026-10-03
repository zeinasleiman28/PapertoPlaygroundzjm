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
  if (/\bNaN\b|undefined|\[object Object\]/.test(t)) acc.bad.push(t.trim().slice(0, 80));
  for (var i = 0; i < n.children.length; i++) __walk(n.children[i], acc);
  return acc;
}
function __clone(v) { return JSON.parse(JSON.stringify(v)); }
function __nonFinite(v, path, out) {
  if (out.length > 4) return;
  if (typeof v === 'number') { if (!isFinite(v)) out.push(path + '=' + v); }
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

  var defaultPanels = 0;
  cases.forEach(function (cs) {
    var bucket = cs.kind === 'edge' ? rep.major : rep.critical;
    var r;
    try { r = compute(__clone(cs.p)); }
    catch (e) { (cs.kind === 'default' ? rep.critical : bucket).push('compute() threw on ' + cs.label + ': ' + e.message); return; }
    if (!r || typeof r !== 'object') { bucket.push('compute() must return an object (' + cs.label + ')'); return; }
    var nf = []; __nonFinite(r, 'r', nf);
    if (nf.length) rep.major.push('compute() returned non-finite numbers on ' + cs.label + ': ' + nf.join(', '));
    if (cs.kind === 'default') {
      (spec.readouts || []).forEach(function (ro) { if (!(ro.key in r)) rep.major.push('readout key "' + ro.key + '" is not returned by compute()'); });
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

  var list = (typeof checks !== 'undefined' && Array.isArray(checks)) ? checks : null;
  if (!list) rep.major.push('CODE does not define const checks = [...]');
  else {
    if (list.length < 2) rep.minor.push('fewer than 2 checks defined');
    var passed = 0, results = [];
    list.forEach(function (c, i) {
      var ok = false, detail = '';
      try {
        var p = merged(c.inputs), r = compute(__clone(p)), res = c.test(r, p);
        if (res && typeof res === 'object') { ok = !!res.pass; detail = res.detail || ''; } else ok = !!res;
      } catch (e) { detail = 'threw: ' + e.message; }
      if (ok) passed++; else rep.major.push('check "' + (c.name || i) + '" fails' + (detail ? ' (' + detail + ')' : '') + '. Fix compute() if the check is right, or fix the check if its expectation is wrong.');
      results.push({ name: c.name, pass: ok });
    });
    rep.stats.checks_passed = passed; rep.stats.checks_total = list.length; rep.stats.check_results = results;
  }
  return JSON.stringify(rep);
}
