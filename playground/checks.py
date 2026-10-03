"""Parse the model output and verify it without a browser."""
import json
import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
CONTROL_TYPES = {"slider", "number", "toggle", "select", "vector", "matrix"}
FORBIDDEN = [
    (r"\bfetch\s*\(", "network call fetch()"), (r"XMLHttpRequest", "XMLHttpRequest"), (r"\bimport\s*[\s({*]", "import"),
    (r"\brequire\s*\(", "require()"), (r"\bdocument\s*\.", "direct DOM access (use V only)"),
    (r"\bwindow\s*\.", "window access"), (r"localStorage|sessionStorage", "browser storage"),
    (r"https?://", "URL inside CODE"), (r"\beval\s*\(", "eval()"), (r"Math\.random", "Math.random (must be deterministic)"),
    (r"</script", "</script inside CODE"),
]


def parse_blocks(text: str):
    """Return (spec_text, code_text); either may be None. 'UNCHANGED' is passed through."""
    text = text.replace("\r\n", "\n")
    spec = code = None
    m = re.search(r"<<<SPEC>>>\s*(.*?)\s*<<<CODE>>>", text, re.S)
    if m:
        spec = m.group(1)
    m = re.search(r"<<<CODE>>>\s*(.*?)\s*(?:<<<END>>>|$)", text, re.S)
    if m:
        code = m.group(1)
    if spec is not None:
        spec = re.sub(r"^```(?:json)?\s*|\s*```$", "", spec.strip())
    if code is not None:
        code = re.sub(r"^```(?:javascript|js)?\s*|\s*```$", "", code.strip())
        code = re.sub(r"^(?:javascript|js|JavaScript|JS)[ \t]*\n", "", code)  # a bare language tag line
    return spec, code


def load_spec(spec_text: str):
    t = (spec_text or "").strip()
    i, j = t.find("{"), t.rfind("}")
    if i > 0 or (j >= 0 and j < len(t) - 1):
        t = t[i:j + 1] if i >= 0 and j > i else t
    err = None
    for cand in (t, re.sub(r",\s*([}\]])", r"\1", t), re.sub(r",\s*([}\]])", r"\1", re.sub(r"(?m)^\s*//.*$", "", t))):
        try:
            return json.loads(cand), None
        except Exception as e:
            err = err or e
    return None, f"SPEC is not valid JSON: {err}"

def autofix(spec: dict, case: dict = None):
    """Deterministic repairs that need no model call. Mutates spec; returns a list of what was fixed."""
    fixed = []
    case = case or {}
    if not str(spec.get("title", "")).strip() and case.get("focus"):
        spec["title"] = str(case["focus"]).split(".")[0][:90]; fixed.append("title from focus")
    for k in ("tagline", "figure_caption"):
        if not isinstance(spec.get(k), str):
            spec[k] = ""
    src = spec.get("source")
    if not isinstance(src, dict):
        spec["source"] = src = {"paper": str(src or "")}
    if case.get("source_url") and not src.get("url"):
        src["url"] = str(case["source_url"])
    sy = spec.get("symbols")
    if isinstance(sy, dict):
        spec["symbols"] = [{"symbol": k, "meaning": v} for k, v in sy.items()]; fixed.append("symbols dict -> list")
    ctl = spec.get("controls") if isinstance(spec.get("controls"), list) else []
    ids = {}
    for c in ctl:
        if not isinstance(c, dict):
            continue
        t, v = c.get("type"), c.get("value")
        if t == "range":
            c["type"] = t = "slider"; fixed.append(f'control {c.get("id")}: type range -> slider')
        if t in ("slider", "number"):
            for k in ("min", "max", "step", "value"):
                if isinstance(c.get(k), str):
                    try:
                        c[k] = float(c[k])
                    except ValueError:
                        pass
            lo, hi, v = c.get("min"), c.get("max"), c.get("value")
            if _num(lo) and _num(hi) and lo > hi:
                c["min"], c["max"] = lo, hi = hi, lo; fixed.append(f'slider {c.get("id")}: swapped min/max')
            if _num(lo) and _num(hi) and _num(v) and not lo <= v <= hi:
                c["value"] = min(hi, max(lo, v)); fixed.append(f'slider {c.get("id")}: default clamped into range')
            if t == "slider" and not _num(c.get("step")) and _num(lo) and _num(hi) and hi > lo:
                c["step"] = (hi - lo) / 100
        elif t == "toggle" and not isinstance(v, bool):
            c["value"] = bool(v) and v not in ("false", "0", 0); fixed.append(f'toggle {c.get("id")}: value -> bool')
        elif t == "select" and isinstance(c.get("options"), list):
            opts = [o if isinstance(o, dict) else {"value": o, "label": str(o)} for o in c["options"]]
            c["options"] = opts
            if opts and v not in [o.get("value") for o in opts]:
                c["value"] = opts[0].get("value"); fixed.append(f'select {c.get("id")}: default -> first option')
        ids[c.get("id")] = c
    ex = spec.get("explorations")
    if isinstance(ex, list):
        if len(ex) > 2:
            spec["explorations"] = ex = ex[:2]; fixed.append("kept first 2 explorations")
        for e in ex:
            if isinstance(e, dict) and isinstance(e.get("preset"), dict):
                bad = [k for k in e["preset"] if k not in ids]
                for k in bad:
                    del e["preset"][k]
                if bad:
                    fixed.append(f"dropped unknown preset keys {bad}")
                for k, val in list(e["preset"].items()):
                    c = ids[k]
                    if c.get("type") == "slider" and _num(val) and _num(c.get("min")) and _num(c.get("max")):
                        nv = min(c["max"], max(c["min"], val))
                        if nv != val:
                            e["preset"][k] = nv; fixed.append(f"preset {k} clamped into range")
    lim = spec.get("limitation")
    if isinstance(lim, str) and lim.strip():
        spec["limitation"] = {"kind": "Limitation", "text": lim}; fixed.append("limitation string -> object")
    elif isinstance(lim, dict) and lim.get("text") and not lim.get("kind"):
        lim["kind"] = "Limitation"
    gr = spec.get("grounding")
    if isinstance(gr, dict):
        for a, b in (("from_excerpt", "from_paper"), ("paper", "from_paper"), ("our", "ours"), ("simplifications", "ours")):
            if b not in gr and a in gr:
                gr[b] = gr.pop(a); fixed.append(f"grounding.{a} -> {b}")
    return fixed


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validate_spec(spec: dict):
    crit, major, minor = [], [], []
    for k in ("title", "idea", "why", "formula", "figure_caption"):
        if not isinstance(spec.get(k), str) or not spec[k].strip():
            (major if k != "figure_caption" else minor).append(f'SPEC field "{k}" is missing or empty')
    src = spec.get("source") or {}
    if not isinstance(src, dict) or not str(src.get("paper", "")).strip():
        major.append('SPEC "source.paper" is missing')
    elif not str(src.get("section", "")).strip() and not str(src.get("equation", "")).strip():
        major.append('SPEC "source" must name the relevant section or equation')
    if not isinstance(spec.get("symbols"), list) or not spec.get("symbols"):
        major.append('SPEC "symbols" must list the meaning of each symbol')

    controls = spec.get("controls")
    ids = set()
    if not isinstance(controls, list) or len(controls) < 2:
        crit.append("SPEC needs at least 2 controls")
        controls = controls if isinstance(controls, list) else []
    for i, c in enumerate(controls):
        if not isinstance(c, dict):
            crit.append(f"control {i} is not an object"); continue
        cid, t = c.get("id"), c.get("type")
        if not isinstance(cid, str) or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", cid or ""):
            crit.append(f"control {i} needs an identifier-like id"); continue
        if cid in ids:
            crit.append(f'duplicate control id "{cid}"')
        ids.add(cid)
        if t not in CONTROL_TYPES:
            crit.append(f'control "{cid}" has unknown type "{t}"'); continue
        v = c.get("value")
        if t == "slider":
            if not all(_num(c.get(k)) for k in ("min", "max", "value")) or c["min"] >= c["max"]:
                crit.append(f'slider "{cid}" needs numeric min < max and value')
            elif not (c["min"] <= v <= c["max"]):
                major.append(f'slider "{cid}" default value is outside [min, max]')
        elif t == "number" and not _num(v):
            crit.append(f'number control "{cid}" needs a numeric value')
        elif t == "toggle" and not isinstance(v, bool):
            crit.append(f'toggle "{cid}" value must be true/false')
        elif t == "select":
            opts = c.get("options")
            if not isinstance(opts, list) or len(opts) < 2 or not all(isinstance(o, dict) and "value" in o for o in opts):
                crit.append(f'select "{cid}" needs >=2 options with value and label')
            elif v not in [o["value"] for o in opts]:
                major.append(f'select "{cid}" default value is not one of its options')
        elif t == "vector":
            if not isinstance(v, list) or not v or not all(_num(x) for x in v):
                crit.append(f'vector "{cid}" value must be a non-empty list of numbers')
        elif t == "matrix":
            if (not isinstance(v, list) or not v or not all(isinstance(r, list) and r for r in v)
                    or len({len(r) for r in v}) != 1 or not all(_num(x) for r in v for x in r)):
                crit.append(f'matrix "{cid}" value must be a rectangular list of number lists')

    ex = spec.get("explorations")
    if not isinstance(ex, list) or len(ex) < 2:
        major.append("SPEC needs exactly 2 explorations")
        ex = ex if isinstance(ex, list) else []
    for i, e in enumerate(ex[:3]):
        if not isinstance(e, dict):
            major.append(f"exploration {i + 1} is not an object"); continue
        for k in ("title", "change", "observe", "why"):
            if not str(e.get(k, "")).strip():
                major.append(f'exploration {i + 1} is missing "{k}"')
        pre = e.get("preset") or {}
        if not isinstance(pre, dict) or not pre:
            minor.append(f"exploration {i + 1} has no preset")
        else:
            bad = [k for k in pre if k not in ids]
            if bad:
                major.append(f"exploration {i + 1} preset uses unknown control ids {bad}; valid ids: {sorted(ids)}")

    lim = spec.get("limitation") or {}
    if not isinstance(lim, dict) or not str(lim.get("text", "")).strip():
        major.append('SPEC "limitation.text" is missing')
    gr = spec.get("grounding") or {}
    if not isinstance(gr, dict) or not gr.get("from_paper"):
        major.append('SPEC "grounding.from_paper" must list statements supported by the excerpt')
    if not isinstance(gr, dict) or not gr.get("ours"):
        major.append('SPEC "grounding.ours" must list our own simplifications/examples')
    ro = spec.get("readouts")
    if not isinstance(ro, list) or not ro:
        major.append('SPEC "readouts" must list computed values to display')
    return crit, major, minor


def static_code(code: str):
    crit, major = [], []
    for pat, what in FORBIDDEN:
        if re.search(pat, code):
            (crit if what.startswith("network") else major).append(f"CODE must not use {what}")
    for name in ("compute", "render"):
        if not re.search(r"function\s+" + name + r"\s*\(|\b" + name + r"\s*=", code):
            crit.append(f"CODE must define {name}")
    if not re.search(r"\bchecks\s*=", code):
        major.append("CODE must define const checks = [...]")
    return crit, major


def run_js(spec: dict, code: str, timeout_s: float = 8.0):
    """Execute compute/render/checks in V8 (mini-racer). Returns report dict, or None if V8 is unavailable."""
    try:
        from py_mini_racer import MiniRacer
    except Exception:
        return None
    ctx = MiniRacer()
    harness = (TEMPLATES / "harness.js").read_text(encoding="utf-8")
    lib = (TEMPLATES / "pg_v.js").read_text(encoding="utf-8")
    rep = {"critical": [], "major": [], "minor": [], "stats": {}}
    try:
        ctx.eval(harness, timeout_sec=timeout_s)
        ctx.eval(lib, timeout_sec=timeout_s)
    except Exception as e:  # our own code; should never happen
        rep["minor"].append(f"harness failed to load: {e}")
        return rep
    try:
        ctx.eval(code, timeout_sec=timeout_s)
    except Exception as e:
        msg = str(e).splitlines()[0][:300] if str(e) else type(e).__name__
        m = re.search(r":(\d+):", msg)
        if m:  # show the offending line so the repair can find it
            ln, lines = int(m.group(1)), code.splitlines()
            ctx_lines = [f"{i + 1}: {lines[i]}" for i in range(max(0, ln - 2), min(len(lines), ln + 1))]
            msg += " | code around it: " + " / ".join(x[:160] for x in ctx_lines)
        rep["critical"].append(f"CODE does not run (syntax or top-level error): {msg}")
        return rep
    try:
        out = ctx.eval("__run(" + json.dumps(spec) + ")", timeout_sec=timeout_s)
        return json.loads(out)
    except Exception as e:
        rep["critical"].append(f"running compute/render/checks failed or timed out: {str(e)[:300]}")
        return rep


def evaluate(spec_in, code_text: str, case: dict = None):
    """Full check. spec_in is SPEC text or an already-parsed dict. Returns dict with critical/major/minor lists,
    stats, the parsed (auto-fixed) spec and the list of deterministic fixes applied."""
    res = {"critical": [], "major": [], "minor": [], "stats": {}, "spec": None, "fixes": []}
    if isinstance(spec_in, dict):
        spec, err = json.loads(json.dumps(spec_in)), None
    else:
        spec, err = load_spec(spec_in or "")
    if err:
        res["critical"].append(err)
        return res
    if not isinstance(spec, dict):
        res["critical"].append("SPEC must be a JSON object")
        return res
    res["fixes"] = autofix(spec, case)
    res["spec"] = spec
    c, m, n = validate_spec(spec)
    res["critical"] += c; res["major"] += m; res["minor"] += n
    if not code_text:
        res["critical"].append("CODE block is missing")
        return res
    c, m = static_code(code_text)
    res["critical"] += c; res["major"] += m
    if any("network" in x for x in c):
        return res
    js = run_js(spec, code_text)
    if js is None:
        res["minor"].append("V8 unavailable: runtime checks skipped")
    else:
        for k in ("critical", "major", "minor"):
            res[k] += js.get(k, [])
        res["stats"] = js.get("stats", {})
        # deterministic fix: drop readouts whose key compute() does not return (no model call needed)
        missing = set(js.get("missing_readouts") or [])
        if missing and len(missing) < len(spec.get("readouts") or []):
            spec["readouts"] = [r for r in spec["readouts"] if not (isinstance(r, dict) and r.get("key") in missing)]
            res["major"] = [x for x in res["major"] if not x.startswith("readout key ")]
            res["fixes"].append(f"dropped readouts not returned by compute(): {sorted(missing)}")
    # de-duplicate while keeping order; collapse the same failure seen on many test inputs
    for k in ("critical", "major", "minor"):
        seen, out = {}, []
        for x in res[k]:
            key = re.sub(r" on (control|random|experiment|default)[^:]*", "", x)
            if key not in seen:
                seen[key] = 1; out.append(x)
        res[k] = out
    return res


def blocks_to_fix(problems):
    """Which block(s) a repair must return: SPEC, CODE or both."""
    need = set()
    for p in problems:
        if "has no effect" in p:
            need.add("CODE")
        elif p.startswith(("SPEC", "control ", "slider", "select", "toggle", "vector", "matrix", "number control",
                         "duplicate control", "exploration")) or "preset uses unknown" in p:
            need.add("SPEC")
        else:
            need.add("CODE")
    return need or {"SPEC", "CODE"}

def unusable(res) -> bool:
    """True if the page would have no working interactive model."""
    if res.get("spec") is None:
        return True
    return any(k in p for p in res["critical"] for k in ("CODE does not run", "CODE block is missing", "on default inputs",
                                                          "drew nothing", "does not define", "failed or timed out"))


def score(res) -> int:
    return 100 * len(res["critical"]) + 10 * len(res["major"]) + len(res["minor"])
