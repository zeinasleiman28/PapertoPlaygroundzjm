# Paper to Playground

An agent that turns a focused research-paper excerpt and a learning brief into a single, self-contained, interactive HTML explanation for an engineering undergraduate.

**Team:** _NAME 1, NAME 2, NAME 3_ (EECE503P / EECE798S)

## Run

```bash
python -m pip install -r requirements.txt
export OPENROUTER_API_KEY=...        # never commit this
python agent.py --input case.json --output out --model MODEL_ID
```

On Windows (PowerShell), with the key in a local `.env` (copy `.env.example`; `.env` is gitignored):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python agent.py --input examples\attention\case.json --output out
```

**MODEL_ID used for development and assessment:** `deepseek/deepseek-v4.1-flash` (via OpenRouter, `https://openrouter.ai/api/v1`). It is the default when `--model` is omitted; override with `--model` or `OPENROUTER_MODEL`.

Outputs: `out/index.html` (works offline in Chromium, no CDN, fonts or remote assets) and `out/trace.jsonl`.
Exit code 0 means a working page was produced; 1 means only a degraded or fallback page could be written; 2 means the input could not be read.

## Architecture

The design keeps model calls few and small, and moves everything that can be verified into deterministic code.

```
case.json ─► locate excerpt ─► 1 generation call ─► offline checks (V8) ─┬─► assemble index.html
             (case field, or      (SPEC JSON +        spec schema,        │
              best-effort URL      compute/render/     static code scan,   └─► repair call(s) with only the
              fetch)               checks JS)          edge-case sweep,         failing items (max 2)
                                                       self-checks
```

1. **Grounding.** The excerpt is read from `case.json` (any field such as `excerpt`; otherwise the longest text field). If no excerpt is supplied, a 4-second best-effort fetch of `source_url` is tried; during assessment this fails fast and the agent continues.
2. **Generation (1 call).** The model returns a JSON *spec* (concept, symbols, controls, readouts, two guided experiments with presets, limitation, grounding split into "stated in the paper" and "our simplifications") and JavaScript defining `compute(p)`, `render(V, p, r)` and `checks`. The model never writes HTML or CSS, which keeps completion tokens low.
3. **Verification (no tokens).** `playground/checks.py` validates the spec and scans the code for forbidden features (network, DOM access, randomness). It then runs the code in V8 through `mini-racer` with a fake DOM (`templates/harness.js`). The harness exercises default inputs, both experiment presets and an edge-case sweep (slider extremes, zero, equal and one-hot vectors, all-zero matrices, toggles, every select option). It verifies that all numbers are finite, that readout keys exist and that figures draw without invalid coordinates, and it runs the model's own known-answer checks.
4. **Revision.** Only if problems remain, a repair call sends back the spec, code and the exact list of failures (the excerpt is not resent). At most two repairs are made, and the best-scoring version is kept.
5. **Assembly.** `playground/build.py` inlines the spec, the generated code, the generic visual library (`templates/pg_v.js`: bar, line, heatmap, diagram, table, worked-arithmetic note) and the app runtime (`templates/pg_app.js`: controls, readouts, presets, live checks) into `templates/page.html`.

**Budget enforcement** (`playground/llm.py`): hard caps of 10 requests, 30,000 completion tokens and a 555-second deadline. Low reasoning effort is requested when the model supports it. Every call logs prompt/completion/reasoning/cached tokens, latency and finish reason to the trace.

**Generic only.** The templates and prompts contain no paper-specific content. Everything about a paper is generated at run time.

## Practice

`examples/cases/` holds practice briefs built from the two public examples plus three extra mechanisms. Run all of them and get a cost/quality table:

```bash
python tools/run_cases.py MODEL_ID
```

## Example input/output

`examples/attention/` contains `case.json` with the generated `index.html` and `trace.jsonl` from one run. Outputs are regenerated fresh during assessment.

## Credits and reuse

- [`requests`](https://requests.readthedocs.io) for HTTP, [`mini-racer`](https://github.com/bpcreech/PyMiniRacer) (V8 for Python) for offline JavaScript checks, and [`pypdf`](https://github.com/py-pdf/pypdf) for best-effort PDF text extraction during development.
- All templates, the visual library and the runtime were written for this project, with help from an AI coding assistant, which the brief allows. No third-party front-end code or assets are embedded in generated pages.
