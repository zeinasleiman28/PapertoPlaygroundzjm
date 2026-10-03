"""Assemble the single self-contained HTML page from the template, the spec and the code."""
import json
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def build_page(spec: dict, code: str) -> str:
    page = _read("page.html")
    spec_json = json.dumps(spec, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    code = (code or "").replace("</script", "<\\/script")
    # Generated code runs in its own classic <script>; if it fails to parse, the app shows an error panel
    # instead of a blank page (pg_app.js guards every call).
    user = code
    return (page.replace("__PG_SPEC_JSON__", spec_json)
                .replace("/*__PG_V__*/", _read("pg_v.js"))
                .replace("/*__PG_USER_CODE__*/", user)
                .replace("/*__PG_APP__*/", _read("pg_app.js")))


def fallback_spec(case: dict, reason: str) -> dict:
    focus = str(case.get("focus", "")).strip()
    return {
        "title": (focus[:90] or "Concept explanation"),
        "tagline": "The interactive model could not be generated automatically for this case.",
        "source": {"paper": str(case.get("title") or case.get("source_url") or ""), "url": str(case.get("source_url", "")),
                   "section": "", "equation": ""},
        "idea": focus or "No learning brief was supplied.",
        "why": "", "formula": "", "symbols": [], "controls": [], "readouts": [],
        "figure_caption": "Generation failed: " + reason,
        "explorations": [], "limitation": {"kind": "Limitation", "text": "This page is a fallback without an interactive model."},
        "grounding": {"from_paper": [], "ours": []},
    }
