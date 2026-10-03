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
    # each block ends at the next marker or the end of the reply (a repair may return only one block)
    m = re.search(r"<<<SPEC>>>\s*(.*?)\s*(?:<<<CODE>>>|<<<CHECKS>>>|<<<END>>>|$)", text, re.S)
    if m:
        spec = m.group(1)
    m = re.search(r"<<<CODE>>>\s*(.*?)\s*(?:<<<SPEC>>>|<<<CHECKS>>>|<<<END>>>|$)", text, re.S)
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

_GREEK = {n: chr(c) for n, c in zip(
    "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho varsigma sigma tau upsilon phi chi psi omega".split(),
    range(0x3B1, 0x3CA))}
_GREEK.update({n.capitalize(): chr(ord(c) - 32) for n, c in _GREEK.items() if n not in ("varsigma",)})
_TEX_SYM = {"cdot": "·", "times": "×", "sum": "Σ", "prod": "Π", "infty": "∞", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
            "neq": "≠", "ne": "≠", "approx": "≈", "propto": "∝", "to": "→", "rightarrow": "→", "partial": "∂", "nabla": "∇",
            "pm": "±", "in": "∈", "sqrt": "√", "|": "‖", "varepsilon": "ε", "varphi": "φ", "ell": "ℓ", "int": "∫", "mid": "|"}


def delatex(s: str) -> str:
    """Turn common inline LaTeX into the page's Unicode + <sub>/<sup> text. Text without LaTeX is returned as is."""
    if not isinstance(s, str) or "{r." in s or not re.search(r"\\[A-Za-z|]|[\^_]\{", s):
        return s
    t = re.sub(r"\$+", "", s)
    t = re.sub(r"\\(?:begin|end)\{[^}]*\}|\\(?:left|right|displaystyle|quad|qquad|nonumber)\b|\\[,;:! ]", " ", t)
    t = re.sub(r"\\tag\{([^}]*)\}", r"(\1)", t)
    t = re.sub(r"\\(?:mathrm|mathbf|mathit|text|operatorname|boldsymbol|mathcal|mathbb)\{([^{}]*)\}", r"\1", t)
    for _ in range(3):  # innermost first; nested fractions need a few passes
        t = re.sub(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", t)
        t = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", t)
    t = re.sub(r"\\([A-Za-z]+|\|)", lambda m: _GREEK.get(m.group(1), _TEX_SYM.get(m.group(1), m.group(1))), t)
    t = re.sub(r"\^\{([^{}]*)\}|\^(\S)", lambda m: "<sup>" + (m.group(1) if m.group(1) is not None else m.group(2)) + "</sup>", t)
    t = re.sub(r"_\{([^{}]*)\}|_([A-Za-z0-9])", lambda m: "<sub>" + (m.group(1) if m.group(1) is not None else m.group(2)) + "</sub>", t)
    # (a)/(b) -> a/b for simple parts; right after a function name (log, exp, ...) keep one pair: log(a/b)
    t = re.sub(r"(\b[A-Za-z]{2,} ?)?\(([A-Za-z0-9.αβγδεθλμνπρστφχψωΣ<>/]+)\)/\(([A-Za-z0-9.αβγδεθλμνπρστφχψωΣ<>/]+)\)",
               lambda m: (m.group(1).rstrip() + "(" + m.group(2) + "/" + m.group(3) + ")") if m.group(1)
               else m.group(2) + "/" + m.group(3), t)
    return re.sub(r"\s+", " ", t.replace("{", "").replace("}", "")).strip()


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
    if not isinstance(spec.get("brief"), list):
        for alt in ("brief_requirements", "requirements", "brief_map", "brief_coverage", "coverage"):
            if isinstance(spec.get(alt), list):
                spec["brief"] = spec.pop(alt); fixed.append(f"{alt} -> brief"); break
    if isinstance(spec.get("brief"), list):
        conv = []
        for b in spec["brief"]:
            if isinstance(b, str):  # "req -> control: x, check: y" style strings
                item = {"req": re.split(r"\s*(?:->|=>|:)\s*", b, 1)[0][:120]}
                for k in ("control", "output", "exploration", "check"):
                    mm = re.search(k + r"s?\s*[:=]\s*\"?([^,;\"\)]+)", b, re.I)
                    if mm:
                        item[k] = mm.group(1).strip()
                conv.append(item)
            else:
                conv.append(b)
        if any(isinstance(b, str) for b in spec["brief"]):
            fixed.append("brief strings -> objects")
        spec["brief"] = conv
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
    if isinstance(gr, list):  # a bare list of claims: treat it as the excerpt-supported part
        spec["grounding"] = gr = {"from_paper": gr}; fixed.append("grounding list -> object")
    elif gr is not None and not isinstance(gr, dict):
        spec["grounding"] = gr = {}; fixed.append("grounding dropped (not an object)")
    if isinstance(gr, dict):
        for a, b in (("from_excerpt", "from_paper"), ("paper", "from_paper"), ("our", "ours"), ("simplifications", "ours")):
            if b not in gr and a in gr:
                gr[b] = gr.pop(a); fixed.append(f"grounding.{a} -> {b}")
        for k in ("from_paper", "ours"):  # the page iterates these: a single string must become a list
            if isinstance(gr.get(k), (str, dict)):
                gr[k] = [gr[k]]; fixed.append(f"grounding.{k} -> list")
    # raw LaTeX is not rendered by the page: convert it to Unicode with <sub>/<sup>
    n_tex = [0]

    def tex(obj, key):
        if isinstance(obj, dict) and isinstance(obj.get(key), str):
            new = delatex(obj[key])
            if new != obj[key]:
                obj[key] = new; n_tex[0] += 1
    for k in ("title", "tagline", "idea", "why", "formula", "figure_caption"):
        tex(spec, k)
    for k in ("paper", "section", "equation"):
        tex(spec.get("source"), k)
    for s in spec.get("symbols") or []:
        tex(s, "symbol"); tex(s, "meaning")
    for lst, key in ((spec.get("controls"), "label"), (spec.get("readouts"), "label")):
        for c in lst if isinstance(lst, list) else []:
            tex(c, key)
    for e in spec.get("explorations") if isinstance(spec.get("explorations"), list) else []:
        for k in ("title", "predict", "change", "observe", "why"):
            tex(e, k)
    tex(spec.get("limitation"), "text")
    for k in ("from_paper", "ours"):
        lst = (spec.get("grounding") or {}).get(k) if isinstance(spec.get("grounding"), dict) else None
        for i, g in enumerate(lst if isinstance(lst, list) else []):
            if isinstance(g, str):
                lst[i] = delatex(g); n_tex[0] += lst[i] != g
            else:
                tex(g, "claim"); tex(g, "where")
    if n_tex[0]:
        fixed.append(f"converted LaTeX to readable text in {n_tex[0]} fields")
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


def grounding_checks(spec: dict, case: dict, source_text: str, fixes: list = None):
    """Cheap fidelity checks: cited numbers must exist in the source, and the focus's explicit asks must be mapped."""
    major = []
    focus = str((case or {}).get("focus", ""))
    hay = " ".join([source_text or ""] + [str(v) for v in (case or {}).values() if isinstance(v, str)])
    if (source_text or "").strip():  # without an excerpt there is nothing to verify citations against
        src = spec.get("source") or {}
        fields = [("source.section", src.get("section")), ("source.equation", src.get("equation"))]
        gr = spec.get("grounding") or {}
        for g in gr.get("from_paper") or []:
            if isinstance(g, dict):
                fields.append(("grounding where", g.get("where")))
        bad = []

        def unverified(val):
            return [tok for tok in re.findall(r"\d+(?:\.\d+)+|(?<=\()\d+(?=\))|(?<=Eq\. )\d+|(?<=Equation )\d+|(?<=Section )\d+",
                                              str(val or "")) if not re.search(r"(?<![\d.])" + re.escape(tok) + r"(?![\d])", hay)]
        # deterministic fix: a "where" note with a number the excerpt does not contain falls back to the verified
        # section (or is dropped), so no repair call is spent on it; source.section/equation still need a repair
        sec = str(src.get("section") or "")
        for g in gr.get("from_paper") or []:
            if isinstance(g, dict) and g.get("where") and unverified(g["where"]):
                old = g["where"]
                g["where"] = sec if sec and not unverified(sec) else ""
                if fixes is not None:
                    fixes.append(f"citation '{old}' not in excerpt -> '{g['where']}'")
        fields = [f for f in fields if f[0] != "grounding where"]
        for name, val in fields:
            for tok in unverified(val):
                bad.append(f"{name} '{val}' ({tok})")
        if bad:
            major.append("SPEC cites numbers not found in the excerpt or focus: " + "; ".join(sorted(set(bad))[:4]) +
                         ". Cite section/equation numbers exactly as written there, or omit the number.")
    brief = [b for b in spec.get("brief") or [] if isinstance(b, dict)]
    if brief and focus:
        f = focus.lower()
        if re.search(r"\bcheck\b|\bverify\b|\bconfirm\b", f) and not any(b.get("check") for b in brief):
            major.append('the focus asks for checks ("Check that ...") but no SPEC.brief item maps to a check')
        if re.search(r"\bguide\b|\bwalk (them|the learner) through\b", f) and not any(b.get("exploration") for b in brief):
            major.append('the focus asks to guide the learner but no SPEC.brief item maps to an exploration')
        if re.search(r"on/off|switch\w* .{0,40}\b(on|off)\b|\btoggle\b", f) and not any(
                isinstance(c, dict) and c.get("type") in ("toggle", "select") for c in spec.get("controls") or []):
            major.append("the focus asks for something to be switched on/off but there is no toggle control")
    return major


def summarize_checks(res: dict) -> dict:
    """Named check groups with pass/fail, for a readable trace."""
    st, probs = res.get("stats", {}), res["critical"] + res["major"]
    def n(*keys):
        return sum(1 for p in probs if any(k in p for k in keys))
    out = {
        "spec_schema": "pass" if not n("SPEC field", "SPEC needs", "SPEC \"", "control ", "slider", "select", "exploration ") else "fail",
        "code_safety": "pass" if not n("CODE must not", "CODE must define", "CODE does not run") else "fail",
        "runs_on_all_test_inputs": f'{st.get("cases", 0)} input states, ' + ("pass" if not n("threw", "NaN", "invalid coordinates", "drew nothing") else "fail"),
        "controls_effective": f'{st.get("controls_effective", 0)}/{st.get("controls_total", 0)}',
        "self_tests": f'{st.get("checks_passed", 0)}/{st.get("checks_total", 0)}',
        "live_numbers_resolve": "pass" if not n("placeholder") else "fail",
        "citations_in_source": "pass" if not n("SPEC cites numbers") else "fail",
        "live_worked_equation": ("pass" if st.get("worked_ok") else "absent") +
                                (f' (blank on {st["worked_bad_states"]} test states)' if st.get("worked_ok") and st.get("worked_bad_states") else ""),
        "predict_first_explorations": f'{st.get("predict_prompts", 0)}/{len((res.get("spec") or {}).get("explorations") or [])}',
    }
    b = st.get("brief")
    if b:
        out["brief_coverage"] = f'{b.get("covered", 0)}/{b.get("items", 0)}'
    return out


def evaluate(spec_in, code_text: str, case: dict = None, source_text: str = ""):
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
    res["major"] += grounding_checks(spec, case, source_text, res["fixes"])
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
        # deterministic fix: a worked equation whose placeholders do not resolve is dropped rather than repaired
        if spec.get("worked") is not None and (not isinstance(spec["worked"], str) or res["stats"].get("worked_ok") is False):
            spec.pop("worked")
            res["stats"]["worked_ok"] = None
            res["fixes"].append("dropped worked equation (placeholders did not resolve)")
    if not spec.get("worked"):
        res["minor"].append('SPEC "worked" (the key equation with live {r.key} values) is missing')
    ex = spec.get("explorations") if isinstance(spec.get("explorations"), list) else []
    res["stats"]["predict_prompts"] = sum(1 for e in ex if isinstance(e, dict) and str(e.get("predict", "")).strip())
    if ex and res["stats"]["predict_prompts"] < len(ex):
        res["minor"].append("an exploration has no \"predict\" question")
    res["summary"] = summarize_checks(res)
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
        elif p.startswith(("brief requirement", "the focus asks")) or " compares states:" in p:
            need.update({"SPEC", "CODE"})
        elif p.startswith(("SPEC", "control ", "slider", "select", "toggle", "vector", "matrix", "number control",
                         "duplicate control", "exploration")) or "preset uses unknown" in p:
            need.add("SPEC")
        else:
            need.add("CODE")
    return need or {"SPEC", "CODE"}

def splice_checks(code: str, new_checks: str):
    """Replace the `checks` declaration in code with new_checks (a full `const checks = [...]` statement).
    Returns the new code, or None if the declaration cannot be located safely."""
    m = re.search(r"(?:const|let|var)\s+checks\s*=\s*\[", code or "")
    n = re.search(r"(?:const|let|var)\s+checks\s*=\s*\[", new_checks or "")
    if not m or not n:
        return None
    i, depth, quote = m.end() - 1, 0, None
    while i < len(code):
        ch = code[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                end = i + 1
                if code[end:end + 1] == ";":
                    end += 1
                return code[:m.start()] + new_checks.strip() + code[end:]
        i += 1
    return None


def only_self_checks(problems) -> bool:
    return bool(problems) and all(re.match(r'check ".*?" fails', p) for p in problems)


def unusable(res) -> bool:
    """True if the page would have no working interactive model."""
    if res.get("spec") is None:
        return True
    return any(k in p for p in res["critical"] for k in ("CODE does not run", "CODE block is missing", "on default inputs",
                                                          "drew nothing", "does not define", "failed or timed out"))


def score(res) -> int:
    return 100 * len(res["critical"]) + 10 * len(res["major"]) + len(res["minor"])
