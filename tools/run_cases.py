"""Practice runner: runs agent.py on every case in examples/cases and prints a cost/quality table.

Usage:  python tools/run_cases.py MODEL_ID [case_name ...]
Outputs go to runs/<case>/ (git-ignored).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    model, names = sys.argv[1], sys.argv[2:]
    cases = sorted((ROOT / "examples" / "cases").glob("*.json"))
    if names:
        cases = [c for c in cases if c.stem in names]
    rows = []
    for case in cases:
        out = ROOT / "runs" / case.stem
        if out.exists():
            for f in out.iterdir():
                f.unlink()
        t = time.time()
        proc = subprocess.run([sys.executable, str(ROOT / "agent.py"), "--input", str(case), "--output", str(out),
                               "--model", model], cwd=ROOT)
        dt = time.time() - t
        summary, checks = {}, []
        for line in (out / "trace.jsonl").read_text(encoding="utf-8").splitlines():
            ev = json.loads(line)
            if ev["action"] == "summary":
                summary = ev
            if ev["action"] == "run_checks":
                checks.append(f'{ev["critical"]}/{ev["major"]}/{ev["minor"]}')
        rows.append((case.stem, proc.returncode, summary.get("requests"), summary.get("total_tokens"),
                     summary.get("completion_tokens"), round(dt, 1), " -> ".join(checks)))
    print(f'\n{"case":<12}{"exit":>5}{"calls":>6}{"tokens":>8}{"compl":>7}{"secs":>7}  checks crit/major/minor per round')
    for r in rows:
        print(f"{r[0]:<12}{r[1]:>5}{str(r[2]):>6}{str(r[3]):>8}{str(r[4]):>7}{r[5]:>7}  {r[6]}")
    print("\nOpen runs/<case>/index.html in Chromium to review each page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
