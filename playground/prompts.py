"""Prompts. Generic: no paper-specific content. Kept short because every prompt token is scored."""
import json

CONTRACT = r"""Build ONE interactive teaching page for a single mechanism from a paper. A fixed template renders it; you write only content (SPEC JSON) and math/plots (CODE). Reply with exactly:
<<<SPEC>>>
{json}
<<<CODE>>>
javascript
<<<END>>>

SPEC (text may use <sub><sup><b><i><code><br> and Unicode math):
{"title","tagline":one sentence,
"source":{"paper","authors","url","section","equation"},
"idea":2-4 sentences for the audience,"why":1-2 sentences,
"formula":the excerpt's key equation, same notation,
"symbols":[{"symbol","meaning"}] every symbol in formula, controls and figure,
"controls":2-4 of {"id","type":"slider","label","min","max","step","value"} | {"id","type":"toggle","label","value":bool} | {"id","type":"select","label","options":[{"value","label"}],"value"} | {"id","type":"vector","label","value":[nums],"min","max","step","resizable"?:{"min","max","fill"}} | {"id","type":"matrix","label","value":[[nums]],"rowLabels","colLabels","min","max","step"},
"readouts":[{"key":compute() output key,"label","digits"?}] 3-6 intermediate and final values,
"figure_caption":how to read the figure,
"explorations":exactly 2 {"title","preset":{control id:value},"change","observe":concrete numbers/shapes the learner will see,"why":the cause},
"limitation":{"kind":"Limitation"|"Assumption"|"Common misunderstanding","text"},
"grounding":{"from_paper":[{"claim","where"}] 2-4, only what the excerpt states,"ours":[2-4 strings: toy values, simplifications]}}

CODE: plain JS, no DOM/network/randomness/imports. Define:
function compute(p){...} // p = {control id: value}. Implement the excerpt's equation exactly; return every intermediate value shown. All numbers finite for every allowed input: handle zeros, equal values, empty sums, log 0 (0·log0=0), overflow (subtract max before exp). Never throw; if input is invalid, normalise/clip and set r.note (string).
function render(V,p,r){...} // r = compute(p). 1-3 panels showing cause and effect, labelled axes:
 V.bars({title,labels,values|series:[{name,values}],highlight,yLabel,xLabel,min,max,digits,refLines:[{y,label}]})
 V.line({title,series:[{name,x,y,dashed}],points:[{x,y,label}],vlines:[{x,label}],hlines:[{y,label}],xLabel,yLabel,xmin,xmax,ymin,ymax}) // a sweep of one input with the current value marked is often clearest
 V.heatmap({title,matrix,rowLabels,colLabels,min,max,digits})
 V.diagram({title,width,height,items:[{type:"rect",x,y,w,h,label,sub}|{type:"circle",cx,cy,r,label}|{type:"arrow"|"line",x1,y1,x2,y2,label,width}|{type:"text",x,y,text}]})
 V.table({title,columns,rows,digits}); V.note(html) // one line of worked arithmetic with live numbers; V.fmt(x,d)
const checks=[{name,inputs:{control id:value},test:(r,p)=>bool}]; // 3-5 known-answer checks from the brief/theory

Rules: stay on the requested focus and audience; define terms before use; match the excerpt's notation; never invent results; every number shown comes from compute(); each control must change compute() output; presets use real control ids with values of the right shape. Be concise."""

SYSTEM = CONTRACT


def user_prompt(case: dict, excerpt_key, excerpt: str, excerpt_note: str) -> str:
    lines = []
    for k, v in case.items():
        if k == excerpt_key:
            continue
        if isinstance(v, (str, int, float)) and str(v).strip():
            lines.append(f"{k}: {str(v).strip()[:1500]}")
    if excerpt:
        lines.append("EXCERPT (ground from_paper claims only in this):\n" + excerpt)
    else:
        lines.append("EXCERPT: unavailable (" + excerpt_note + "). Use only well-established content of the cited "
                     "section; keep from_paper conservative.")
    return "\n".join(lines)


REPAIR_SYSTEM = ("You fix a generated teaching page made of SPEC (JSON) and CODE (JS: compute(p), render(V,p,r), "
                 "const checks). Fix the root cause of each failure; if a check's expected value is wrong, fix the "
                 "check, never weaken a true property. Reply with only the requested block(s) in the format "
                 "<<<SPEC>>>json<<<CODE>>>js<<<END>>>; write UNCHANGED as the body of a block you do not change.")


def repair_prompt(spec: dict, code_text: str, problems: list, focus: str, blocks: set) -> str:
    probs = "\n".join(f"- {p}" for p in problems[:10])
    s = f"Focus: {focus[:400]}\nFailed checks:\n{probs}\n"
    if "SPEC" in blocks:
        s += "\nSPEC:\n" + json.dumps(spec, ensure_ascii=False, separators=(",", ":")) + "\n"
    else:
        ctl = [{k: c.get(k) for k in ("id", "type", "value", "min", "max", "options") if k in c}
               for c in spec.get("controls", []) if isinstance(c, dict)]
        s += "\nControls (SPEC unchanged): " + json.dumps(ctl, separators=(",", ":"))
        s += "\nReadout keys: " + json.dumps([r.get("key") for r in spec.get("readouts", []) if isinstance(r, dict)]) + "\n"
    if "CODE" in blocks:
        s += "\nCODE:\n" + code_text + "\n"
    want = " and ".join(sorted(blocks))
    return s + f"\nReturn the corrected {want} (full block{'s' if len(blocks) > 1 else ''}); the other block: UNCHANGED."
