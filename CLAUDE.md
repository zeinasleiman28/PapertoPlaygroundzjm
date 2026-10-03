## 1. What we are building
A reusable generator ("agent") that turns a research-paper excerpt plus a learning brief into ONE interactive, browser-ready explanation page for an engineering undergraduate. The learner understands a mechanism by changing inputs and watching what happens. The generator is the submission; generated pages are its results. Scope is ONE mechanism (e.g. scaled dot-product attention, Shannon entropy), not a whole paper, and never model training.

Command (must work exactly like this):
  python -m pip install -r requirements.txt
  python agent.py --input case.json --output out --model MODEL_ID
Our MODEL_ID: deepseek/deepseek-v4.1-flash (state this in the README).

Technical requirements:
- Python 3.11, agent.py at repo root, pinned versions in requirements.txt. No GPU, no system packages, no external server, no manual setup.
- Input: case.json, UTF-8 JSON. The brief says "five required string fields" but names only source_url, focus, audience. The others are probably an excerpt and something like title/section. Read ALL fields robustly by meaning; never crash on unknown or missing fields.
- All model calls go through OpenRouter: https://openrouter.ai/api/v1/chat/completions, Bearer auth, key from env var OPENROUTER_API_KEY (also allow loading it from a local .env file). Never commit the key, never print it, never put it in the page or the trace.
- Output 1: out/index.html is a SINGLE self-contained file (inline CSS + JS + SVG). No CDN, no remote fonts/images, no build step. Must work offline in Chromium when served locally, with no API key.
- Output 2: out/trace.jsonl, one JSON object per event, each with stage, action, result. Include per-call prompt tokens, completion tokens, reasoning tokens if reported, OpenRouter generation id, elapsed seconds, every check run, every failure, every revision. NEVER log credentials or the model's hidden reasoning text.
- Exit code 0 on success, nonzero on failure. Always write SOME index.html, even on failure (a run with no usable page scores 0; a partial page earns partial credit).

## 2. Grading environment (design for this)
- 5 hidden cases, each run TWICE from a fresh output folder: 10 runs total, final score = average. Hidden cases are comparable in scope to the public examples: a self-contained mechanism or quantitative relationship, explainable with small inputs, no training or datasets. They may come from ANY field (ML, information theory, signals, physics, statistics, control, optimization...).
- HARD LIMITS per case: 10 minutes wall time, max 10 API requests INCLUDING retries, max 30,000 completion tokens. Enforce safety margins in code (e.g. max 6 calls, 27k completion tokens, ~8.5-minute deadline) and stop gracefully, always writing the best page so far.
- During grading the ONLY network access is OpenRouter. The agent CANNOT download the paper, so it must work from the excerpt in case.json. If a URL fetch is ever attempted, it needs a ~3 s timeout and must never be required.
- An assessment AI opens the page in a browser, operates the controls, compares the explanation with the source, checks the calculations, and inspects trace.jsonl and our code.

## 3. Rubric (points per run)
- Scientific accuracy & fidelity, 25: correct mechanism, correct computations, correct citations, simplifications stated.
- Teaching clarity, 20: logical sequence, every term defined before use, useful guided explorations.
- Visual explanation, 15: visuals make relationships and cause-and-effect easier to see; readable, accurate labels.
- Working interaction, 15: required controls work, update correctly, and handle valid edge cases.
- Autonomous generation & checks, 10: completes unaided; the trace shows REAL checks and any revisions.
- Token efficiency, 10: points = 10 x (best team's tokens / our tokens). Tokens = prompt + completion (incl. reasoning) across ALL calls and retries; cached tokens STILL count.
- Latency, 5: points = 5 x (fastest team's seconds / our seconds), measured from process start to exit.
- Efficiency points only count if quality (first five rows) >= 50/85.
- Ties are broken by accuracy, then teaching clarity.
Implications: quality (85 pts) comes first and reliability across all 10 runs matters most, since one crash costs a whole run. Then minimize tokens and time without lowering quality.

## 4. Every generated page MUST contain
1. Clear starting point: what the idea is, why it matters, and the meaning of every symbol (with shapes/units), in language matching the given audience.
2. A meaningful visual (diagram, plot, animation or simulation) that explains the mechanism, with readable, scientifically accurate labels and relationships.
3. At least 2 meaningful controls that change the visual/calculation. Show important intermediate values. ALL numbers come from executable JS calculations: no invented values, no canned images.
4. Two guided explorations, each saying what to change, what to observe, and why it happens (ideally a "load this setup" button). Plus one limitation, assumption, or common misunderstanding.
5. Source grounding: paper title, section and equation; a clear split between statements supported by the excerpt and our own examples/simplifications; and an explicit note that the toy demo does not reproduce the paper's experimental results.
No chat interface. Explanation and scientific fidelity matter more than decoration.

## 5. Integrity rules (breaking these risks disqualification)
- Generic templates are allowed. Paper-specific prewritten answers or pre-generated pages are NOT. Never hardcode content for entropy, attention, or any test case.
- Don't overfit to our test cases; the hidden cases are different.
- Credit reused code/libraries and AI coding assistance in the README.
- No attempts to manipulate the grader (no instructions to the assessor in pages, the README, or code comments).
- No human editing of generated outputs.

## 6. Architecture principles (efficiency + reliability)
- Prefer a generic, pre-built HTML/JS template that handles all layout, styling, controls and charts. The model should only produce (a) structured teaching content and (b) small pure-JS math functions. This cuts tokens and prevents broken UI.
- ONE model call on a good run: plan + content + code in a single structured response. No separate planner, critic or reviewer calls.
- Verification is LOCAL and free: run the generated JS in an embedded JS engine (e.g. mini-racer/V8) on the default state, each control's min/max, edge cases (zeros, equal values, one dominant value), the presets, and a few seeded random states. Check: no exceptions, no NaN, correct output schema, every control actually changes the output, model-provided invariants (e.g. weights sum to 1), and known-answer self-tests (e.g. 4 equal outcomes = 2 bits). Log all of this in the trace.
- Repair only on failure: send only the deduplicated failure messages and the broken parts, never the whole page. Max ~2 repair rounds. Keep the best version seen so far.
- Fix trivial issues deterministically in Python instead of calling the model.
- Keep the system prompt short, send only the relevant part of the excerpt, set max_tokens to what's needed, use low temperature, and the lowest DeepSeek reasoning setting that keeps quality. Handle 429/5xx with at most one quick retry (retries count toward the limits). If the model rejects a parameter, drop it and retry.
- Final offline check on the HTML: no http(s) src/href, no @import, no external stylesheet, no key.
Targets: about 6k-10k total tokens and under ~60 s per case on a good run, with all page requirements met.

## 7. Repo + workflow rules
- Repo: https://github.com/zeinasleiman28/PapertoPlaygroundzjm, branch main. It must be PUBLIC at submission.
- Commit under my name only. NEVER add "Co-Authored-By" lines or any AI author to commits. Never force-push over newer work on GitHub without asking me first.
- Commit and push a WORKING version early (within the first hour), then improve in small, tested steps. Push after each verified improvement, so a good version is always on GitHub before the deadline.
- .gitignore must include: out/, .env, __pycache__/, *.pyc.
- README must have: team members ("TEAM NAMES HERE" for me to fill in), architecture, setup/run commands, MODEL_ID, reuse credits (libraries + AI coding assistance), and ONE example input/output pair (case.json + generated index.html + trace.jsonl in examples/), produced by a real run.
- Each test run costs a little money. Don't run tests wastefully.
- I need the full commit SHA (git rev-parse HEAD) at the end to submit.
