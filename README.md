# Paper to Playground

An agent that turns a focused research-paper excerpt and a learning brief into one self-contained, interactive HTML page that explains a single mechanism to an engineering undergraduate.

**Team members:** Zeina Sleiman, Jad DIa and Michel Samrani (EECE503P / EECE798S)

**MODEL_ID:** `deepseek/deepseek-v4.1-flash` (via OpenRouter). It is also the default when `--model` is omitted.

## Setup and run

```bash
python -m pip install -r requirements.txt
export OPENROUTER_API_KEY=...        # never commit this
python agent.py --input case.json --output out --model deepseek/deepseek-v4.1-flash
```

On Windows you can instead put `OPENROUTER_API_KEY=...` in a local `.env` file (see `.env.example`; `.env` is gitignored), which `agent.py` loads when the variable is not set.

Requirements: Python 3.11, the pinned packages in `requirements.txt`, and no GPU, system packages or server.

**Outputs**
- `out/index.html`: a single self-contained page with inline CSS, JS and SVG. It works offline in Chromium and contains no CDN links, fonts, remote images or API key.
- `out/trace.jsonl`: one JSON event per line with `stage`, `action` and `result`. Every model call records its prompt, completion and reasoning tokens, OpenRouter generation id, latency and finish reason. Every check round, automatic fix, repair and the final summary are also logged. Credentials and hidden reasoning are never logged.

**Exit codes:** 0 means a working page was produced; 1 means only a degraded or fallback page could be written; 2 means `case.json` could not be read. A page is written in every case.

## Architecture

The model writes only teaching content and small pure-JS math functions. A generic, pre-built template handles all layout, controls and charts, and every check runs locally at no token cost.

```
case.json ─► read all fields, locate and trim excerpt ─► 1 generation call ─► local checks in V8 ─┬─► assemble index.html
                                                         (SPEC JSON + JS)    (+ Python autofixes)  │
                                                                                                    └─► targeted repair call (only if a
                                                                                                        check fails; failing block only)
```

1. **Input and grounding** (`playground/source.py`). Reads every field of `case.json`. The excerpt is taken from any excerpt-like field, or else the longest text field. Reference lists are dropped, and long text is cut to the window that best matches the focus (7,000 characters at most). The URL is fetched only when no excerpt is supplied, with a 3-second timeout, and is never required.
2. **One generation call** (`playground/prompts.py`). A short system prompt asks for two blocks:
   - **SPEC** (JSON): title, idea, why it matters, formula, symbol table, 2–4 controls, readouts, two guided experiments with presets, a limitation, and grounding split into "stated in the paper" and "our simplifications".
   - **CODE**: `compute(p)` (the mechanism's maths), `render(V, p, r)` (drawn with the template's chart library) and `checks` (known-answer tests).

   Numbers quoted in the experiment text are written as `{r.key}` placeholders that the page fills from `compute()` at that experiment's preset, so quoted values cannot drift from the real calculation.
3. **Local verification** (`playground/checks.py`, `templates/harness.js`). The generated JS runs in embedded V8 (`mini-racer`) with a fake DOM. The harness exercises:
   - the default inputs and both experiment presets;
   - every slider at its minimum and maximum, and combined extremes (catching 0/0 cases);
   - zero, equal and one-dominant vectors, all-zero and all-one matrices, flipped toggles and every select option;
   - seeded random input states.

   It checks for exceptions, NaN values, NaN or undefined text in figures, missing readouts and unresolved placeholders. It also checks that every control actually changes the calculation or the figure, and runs the model's known-answer checks. The spec is also validated, and the code is scanned for network, DOM, randomness and other forbidden features.
4. **Deterministic fixes before any repair.** Out-of-range defaults, invalid select values, unknown preset keys, missing readouts, wrongly shaped fields and extra experiments are fixed in Python without a model call.
5. **Targeted repair, only on failure.** The agent sends the deduplicated failure messages and only the failing block (SPEC or CODE), with a short repair prompt. It makes at most 2 repairs, stops early if a repair makes no progress, and keeps the best version seen.
   - If only the model's own known-answer tests fail, one cheap repair asks for either a corrected `checks` array, which is spliced into the code, or corrected code if the maths is wrong. If a test still disagrees with a computation that passes every other check, it is left off the page and recorded in the trace.
   - If the page would still be unusable (code that does not run), the agent regenerates once from scratch, within the budget.
6. **Assembly** (`playground/build.py`). The spec, the generated code, the chart library (`templates/pg_v.js`: bars, line plots with optional log axes, heatmaps, diagrams, tables, worked-arithmetic notes) and the runtime (`templates/pg_app.js`: controls, presets, live readouts, live checks) are inlined into `templates/page.html`. A final scan confirms the page has no external resources.

**Limits enforced in code** (`playground/llm.py`), with margins under the assessment limits: at most 6 requests including retries, 27,000 completion tokens, a 510-second model deadline, a 240-second cap per call, and one quick retry on 429/5xx/timeout. Optional parameters that the API rejects are dropped and the call is retried.

**Efficiency settings** (measured on our practice cases):
- Model reasoning is turned off. With `low` or `medium`, DeepSeek spent 5k–27k hidden reasoning tokens per call, which cost 2–6× more and could exhaust the budget before any answer was written.
- OpenRouter is asked to route to the fastest provider.
- A typical good run is 1 call, about 4–5k total tokens and 6–12 seconds.

**Generic only.** The templates and prompts contain no paper-specific content; everything about a paper is generated at run time from the case.

## Example input/output

`examples/attention/` holds `case.json` (public Example A, with a short excerpt paraphrased in our own words) together with the `index.html` and `trace.jsonl` produced by one real run of the command above. That run passed every local check on the first call: 1 request, about 4.5k tokens, about 13 s. Its trace lists each check round. Runs that need repairs log the failing checks, the targeted repair requests and the result of each revision in the same way. Assessed outputs are generated fresh.

`examples/cases/` holds the practice briefs used during development. They cover the two public examples plus softmax temperature, batch normalisation, dropout, Adam, gradient descent, an RC low-pass filter and Bayes' rule, each with a short paraphrased excerpt. `python tools/run_cases.py deepseek/deepseek-v4.1-flash` runs them all and prints a cost table.

## Credits and reuse

- [`requests`](https://requests.readthedocs.io) for HTTP.
- [`mini-racer`](https://github.com/bpcreech/PyMiniRacer) (embedded V8) for running and checking the generated JavaScript offline.
- [`python-dotenv`](https://github.com/theskumar/python-dotenv) for loading a local `.env` file.
- [`pypdf`](https://github.com/py-pdf/pypdf) for best-effort PDF text extraction when a case has no excerpt.
- The agent, prompts, templates, chart library and runtime were written for this project with help from AI coding assistants (Claude), as the brief allows. No third-party front-end code or assets are embedded in generated pages.
