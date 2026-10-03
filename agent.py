#!/usr/bin/env python3
"""Paper to Playground agent.

python agent.py --input case.json --output out --model MODEL_ID

Pipeline: read case -> locate excerpt -> one generation call (spec + code) -> offline checks in V8
-> targeted repair calls only if checks fail -> assemble a single self-contained index.html.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

try:  # optional: load OPENROUTER_API_KEY etc. from a local .env
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from playground import checks as CK
from playground.build import build_page, fallback_spec
from playground.llm import LLM, BudgetExceeded
from playground.prompts import REPAIR_SYSTEM, SYSTEM, repair_prompt, user_prompt
from playground.source import fetch_excerpt, find_excerpt, trim_excerpt

GEN_MAX_TOKENS = int(os.environ.get("P2P_GEN_MAX_TOKENS", "9000"))
REPAIR_MAX_TOKENS = int(os.environ.get("P2P_REPAIR_MAX_TOKENS", "8000"))
MAX_REPAIRS = int(os.environ.get("P2P_MAX_REPAIRS", "2"))
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")


class Trace:
    def __init__(self, path: Path, t0: float):
        self.f = open(path, "w", encoding="utf-8", buffering=1)
        self.t0 = t0

    def event(self, stage: str, action: str, result: str, **extra):
        rec = {"t": round(time.time() - self.t0, 3), "stage": stage, "action": action, "result": result}
        rec.update({k: v for k, v in extra.items() if v is not None})
        self.f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def close(self):
        self.f.close()


def summarize(res):
    return {"critical": len(res["critical"]), "major": len(res["major"]), "minor": len(res["minor"]),
            "score": CK.score(res)}


def log_checks(trace, stage, res, attempt):
    st = res.get("stats", {})
    trace.event(stage, "run_checks", "pass" if not res["critical"] and not res["major"] else "fail",
                attempt=attempt, **summarize(res), problems=(res["critical"] + res["major"] + res["minor"])[:15],
                auto_fixes=res.get("fixes") or None,
                cases_exercised=st.get("cases"), figure_panels=st.get("panels"),
                self_checks=f'{st.get("checks_passed")}/{st.get("checks_total")}' if "checks_total" in st else None,
                self_check_results=st.get("check_results"))


def main() -> int:
    t0 = time.time()
    ap = argparse.ArgumentParser(description="Generate an interactive explanation page from a paper excerpt.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"OpenRouter model ID (default: $OPENROUTER_MODEL or {DEFAULT_MODEL})")
    ap.add_argument("--reasoning", default=os.environ.get("P2P_REASONING", "none"),
                    help="reasoning effort sent to OpenRouter: low|minimal|medium|none|off")
    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    trace = Trace(out / "trace.jsonl", t0)
    trace.event("start", "init", "ok", model=args.model, reasoning=args.reasoning, python=sys.version.split()[0])

    # ---- read case ----
    try:
        case = json.loads(Path(args.input).read_text(encoding="utf-8"))
        assert isinstance(case, dict)
    except Exception as e:
        trace.event("input", "read_case", "error", error=str(e)[:300])
        (out / "index.html").write_text(build_page(fallback_spec({}, "the input case could not be read"), ""), encoding="utf-8")
        trace.event("output", "write_page", "fallback")
        trace.close()
        return 2
    missing = [k for k in ("source_url", "focus", "audience") if not str(case.get(k, "")).strip()]
    trace.event("input", "read_case", "ok" if not missing else "warning", fields=sorted(case.keys()), missing=missing or None)

    # ---- excerpt ----
    ex_key, excerpt = find_excerpt(case)
    note = "supplied in case.json" if excerpt else ""
    if not excerpt:
        excerpt, note = fetch_excerpt(str(case.get("source_url", "")), str(case.get("focus", "")))
    if excerpt:
        excerpt, tnote = trim_excerpt(excerpt, str(case.get("focus", "")))
        note = (note + "; " + tnote).strip("; ") if tnote else note
    trace.event("ground", "locate_excerpt", "ok" if excerpt else "none", source=ex_key or "url", chars=len(excerpt), note=note)

    llm = LLM(args.model, trace, t0, reasoning=args.reasoning)
    focus = str(case.get("focus", ""))
    best = None  # (score, spec_text, code_text, res)
    exit_code = 0

    def consider(spec_text, code_text, res):
        nonlocal best
        if best is None or CK.score(res) < best[0]:
            best = (CK.score(res), spec_text, code_text, res)

    try:
        # ---- generate ----
        prompt = user_prompt(case, ex_key, excerpt, note or "unavailable")
        try:
            raw = llm.chat(SYSTEM, prompt, GEN_MAX_TOKENS, "generate")
        except BudgetExceeded:
            raise
        except Exception as e:  # transient API failure: one more attempt while the budget allows
            trace.event("generate", "retry_after_error", "started", error=str(e)[:200])
            raw = llm.chat(SYSTEM, prompt, GEN_MAX_TOKENS, "generate")
        spec_text, code_text = CK.parse_blocks(raw)
        trace.event("generate", "parse_output", "ok" if spec_text and code_text else "error",
                    spec_chars=len(spec_text or ""), code_chars=len(code_text or ""))
        res = CK.evaluate(spec_text, code_text, case)
        log_checks(trace, "verify", res, 0)
        consider(spec_text, code_text, res)

        # ---- repair loop ----
        attempt = 0
        while (best[3]["critical"] or best[3]["major"]) and attempt < MAX_REPAIRS:
            attempt += 1
            _, s_txt, c_txt, r = best
            problems = r["critical"] + r["major"]
            if r["spec"] is None or not c_txt:
                # Output was truncated or malformed: regenerate from scratch, asking for brevity.
                trace.event("revise", "regenerate", "started", attempt=attempt, reason=problems[:2])
                raw = llm.chat(SYSTEM, user_prompt(case, ex_key, excerpt, note or "unavailable") +
                               "\nYour previous reply was cut off or malformed. Keep text and code compact and follow the block format exactly.",
                               GEN_MAX_TOKENS, "revise")
                s_txt = c_txt = None
            else:
                want = CK.blocks_to_fix(problems)
                trace.event("revise", "request_repair", "started", attempt=attempt, n_problems=len(problems),
                            blocks=sorted(want))
                raw = llm.chat(REPAIR_SYSTEM, repair_prompt(r["spec"], c_txt, problems, focus, want),
                               REPAIR_MAX_TOKENS, "revise")
                s_txt = r["spec"]  # carry deterministic fixes forward
            ns, nc = CK.parse_blocks(raw)
            if ns is None and nc is None and raw.strip():  # model returned a bare block without markers
                ns, nc = (raw, None) if raw.lstrip().startswith("{") else (None, raw)
            ns = s_txt if (ns is None or ns.strip().upper() == "UNCHANGED") else ns
            nc = c_txt if (nc is None or nc.strip().upper() == "UNCHANGED") else nc
            res = CK.evaluate(ns, nc, case)
            log_checks(trace, "verify", res, attempt)
            prev = best[0]
            consider(ns, nc, res)
            trace.event("revise", "apply_repair", "improved" if best[0] < prev else "not_improved",
                        attempt=attempt, score_before=prev, score_after=CK.score(res))
            if best[0] >= prev and sorted(res["critical"] + res["major"]) == sorted(problems):
                # same failures after a repair: another identical request would waste tokens
                trace.event("revise", "stop_repairs", "no_progress", attempt=attempt)
                break
    except BudgetExceeded as e:
        trace.event("budget", "stop", "limit", reason=str(e))
    except Exception as e:
        trace.event("generate", "exception", "error", error=f"{type(e).__name__}: {e}"[:500])

    # ---- assemble ----
    if best and best[3]["spec"] is not None and not any("CODE does not define" in p or "CODE block is missing" in p
                                                         for p in best[3]["critical"]):
        spec, code = best[3]["spec"], best[2]
        if not isinstance(spec.get("source"), dict):
            spec["source"] = {}
        spec["source"].setdefault("url", str(case.get("source_url", "")))
        if not spec["source"].get("url"):
            spec["source"]["url"] = str(case.get("source_url", ""))
        html = build_page(spec, code)
        status = "ok" if not best[3]["critical"] else "degraded"
        broken = [p for p in best[3]["critical"] if "default inputs" in p or "does not run" in p or "not valid JSON" in p]
        if broken:
            exit_code = 1
    else:
        reason = (best[3]["critical"][0] if best and best[3]["critical"] else "no usable model output")
        html = build_page(fallback_spec(case, reason), "")
        status, exit_code = "fallback", 1

    ext = re.findall(r"""(?:src|href)\s*=\s*["']https?://|@import\s+url\(\s*["']?https?://|<link[^>]+stylesheet""", html)
    links_only = all("href" in x for x in ext)  # a plain hyperlink to the paper is fine; resources are not
    (out / "index.html").write_text(html, encoding="utf-8")
    trace.event("output", "write_page", status, bytes=len(html.encode("utf-8")),
                external_resources="none" if (not ext or links_only) else ext[:3],
                remaining_issues=(best[3]["critical"] + best[3]["major"])[:10] if best else None)
    trace.event("done", "summary", status, requests=llm.requests, prompt_tokens=llm.prompt_tokens,
                completion_tokens=llm.completion_tokens, total_tokens=llm.prompt_tokens + llm.completion_tokens,
                elapsed_s=round(time.time() - t0, 2), exit_code=exit_code)
    trace.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
