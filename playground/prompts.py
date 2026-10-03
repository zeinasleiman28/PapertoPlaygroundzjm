"""Prompts. Generic: no paper-specific content."""

CONTRACT = r"""
You build ONE interactive teaching page that explains a single mechanism from a research paper.
A fixed HTML template renders everything; you supply a SPEC (JSON) and CODE (JavaScript).

Reply with exactly these two blocks and nothing else:
<<<SPEC>>>
{...json...}
<<<CODE>>>
...javascript...
<<<END>>>

SPEC fields (all text may use only <sub> <sup> <b> <i> <em> <code> <br> tags and Unicode math such as θ Σ √ ≤ ·):
{
 "title": short, names the concept,
 "tagline": one sentence on what the learner will see,
 "source": {"paper": title, "authors": short, "url": the source_url, "section": e.g. "Section 3.2.1", "equation": e.g. "Eq. (1)" or ""},
 "idea": 2-4 short sentences for the audience; blank line separates paragraphs,
 "why": 1-3 sentences on why it matters,
 "formula": the paper's key equation in inline HTML,
 "symbols": [{"symbol": ..., "meaning": ...}] every symbol in the formula and controls,
 "controls": >=2 items, each one of
   {"id","type":"slider","label","min","max","step","value","unit"?, "help"?}
   {"id","type":"number","label","value","min"?,"max"?,"step"?}
   {"id","type":"toggle","label","value":true|false}
   {"id","type":"select","label","options":[{"value":..,"label":..}],"value":..}
   {"id","type":"vector","label","value":[numbers],"labels"?:[..],"min"?,"max"?,"step"?,"resizable"?:{"min":n,"max":n,"fill":number}}
   {"id","type":"matrix","label","value":[[numbers]],"rowLabels"?,"colLabels"?,"min"?,"max"?,"step"?}
 "readouts": [{"key": output key from compute, "label", "unit"?, "digits"?}] 3-8 important intermediate and final values (scalar, array or matrix),
 "figure_caption": 1-2 sentences: how to read the figure,
 "explorations": exactly 2, each {"title","preset":{control id: value, ...},"change","observe","why"}; preset puts the controls into the start state; "observe" names concrete numbers or shapes the learner will see,
 "limitation": {"kind": "Limitation"|"Assumption"|"Common misunderstanding", "text"},
 "grounding": {"from_paper": [{"claim", "where": section/equation}] 2-4 items, only things the excerpt actually states; "ours": [strings] 2-4 items: toy sizes, chosen numbers, simplifications, anything not in the excerpt}
}

CODE must define exactly these three globals, in plain ES2017, no imports, no DOM, no network, no randomness:
function compute(p) { ... return {...}; }
  p: {control id: current value}. Pure and deterministic. Implement the paper's equation exactly, step by step,
  and return every intermediate quantity the figure and readouts show. Handle edge cases (zeros, equal values,
  empty sums, log(0)) so every returned number is finite; use the paper's convention (e.g. 0·log 0 = 0).
  Validate inputs instead of throwing (e.g. normalise or clip, and return a string field "note" explaining it).
function render(V, p, r) { ... }
  Draw with V only (r = compute(p)). Use 1-3 panels that make cause and effect visible. Available:
  V.bars({title, labels, values | series:[{name,values,tone}], highlight: index|[indices], yLabel, xLabel, min, max, digits, refLines:[{y,label}]})
  V.line({title, series:[{name,x:[..],y:[..],tone,dashed}], points:[{x,y,label,tone}], vlines:[{x,label}], hlines:[{y,label}], xLabel, yLabel, xmin, xmax, ymin, ymax})
  V.heatmap({title, matrix, rowLabels, colLabels, min, max, digits, highlight:[[row,col]]})
  V.diagram({title, width, height, items:[{type:"rect",x,y,w,h,label,sub,tone}, {type:"circle",cx,cy,r,label,tone},
     {type:"arrow"|"line",x1,y1,x2,y2,label,tone,width,dashed}, {type:"text",x,y,text,size,anchor,tone}, {type:"path",d,tone,fill}]})
  V.table({title, columns:[..], rows:[[..]], highlightRow, digits})
  V.note(html, tone)  // one line of worked arithmetic with live numbers, e.g. "H = 0.5·1 + 0.5·1 = 1 bit"
  V.fmt(x, digits) formats numbers. tone is one of accent|alt|ours|muted|warn|ink. SVG labels are plain text (use Unicode subscripts like q₁).
  A sweep line plot (vary one input over a range, mark the current value with points) is often the clearest cause-and-effect view.
const checks = [ {name, inputs:{control id: value}, test:(r,p)=> true|false | {pass, detail}} ];
  3-6 checks with known answers from the brief or from hand calculation (identities, limits, sums, special cases).
  inputs override the default control values.

Rules:
- Explain only the requested concept for the stated audience; define every term before using it; be concise.
- Scientific fidelity first: match the excerpt's notation and equation; never invent results or citations.
- Numbers shown must come from compute(); never hard-code results in text that changes with inputs.
- Keep default values small and readable; slider ranges must keep everything finite.
- Explorations must use real control ids in "preset" with values of the right type and shape.
"""

SYSTEM = "You are a careful scientific explainer and front-end engineer. Follow the output contract exactly." + CONTRACT


def user_prompt(case: dict, excerpt_key, excerpt: str, excerpt_note: str) -> str:
    lines = ["CASE"]
    for k, v in case.items():
        if k == excerpt_key:
            continue
        if isinstance(v, (str, int, float)) and str(v).strip():
            lines.append(f"{k}: {str(v).strip()}")
    lines.append("")
    if excerpt:
        lines.append("SOURCE EXCERPT (ground every 'from_paper' claim in this text):")
        lines.append(excerpt)
    else:
        lines.append("SOURCE EXCERPT: not available (" + excerpt_note + "). Use only well-established content of the "
                     "cited paper, keep 'from_paper' claims conservative, and mark anything uncertain under 'ours'.")
    lines.append("")
    lines.append("Write the SPEC and CODE now.")
    return "\n".join(lines)


REPAIR_SYSTEM = "You fix a generated teaching page. Follow the output contract exactly." + CONTRACT


def repair_prompt(spec_text: str, code_text: str, problems: list, focus: str) -> str:
    probs = "\n".join(f"- {p}" for p in problems[:12])
    return (
        f"Learning brief: {focus}\n\n"
        "Automatic checks found these problems in the page you produced:\n"
        f"{probs}\n\n"
        "Current SPEC:\n" + spec_text + "\n\nCurrent CODE:\n" + code_text + "\n\n"
        "Fix every problem. Return BOTH blocks in the same format (<<<SPEC>>> ... <<<CODE>>> ... <<<END>>>). "
        "If a block needs no change you may write the single word UNCHANGED as its body."
    )
