# The Right to Dissent

Research implementation for **Preventing Premature Consensus in LLM Multi-Agent Teams**. The repository supports a 600-question hybrid study, two-stage collection, nine protocol conditions, repeated homogeneous model teams, audited retries, and an executable statistical notebook.

The software has been tested with offline fixtures. **No live experiment or empirical claim is implied by those results.** Model/provider compatibility, task difficulty and relevant minority-case prevalence must be established in a separate live preflight/development study.

## Start here

- [Study-01 recovery plan](docs/recovery-plan.md), [Blue Sky paper draft](paper/blue-sky/README.md), and [offline recovery notebook](notebooks/recovery_review.ipynb). These preserve the original results and clearly distinguish the proposed persistent-challenge protocol from collected evidence.
- [Interactive experiment notebook for Anaconda](notebooks/run_experiment.ipynb): run collection, see progress, and view statistical results in one notebook. Includes environment setup and offline demo, live preflight, and full-study modes.
- [Research workflow and statistical specification](docs/research-workflow.md)
- [Study configuration](configs/study.json)
- [Statistical reporting notebook](notebooks/research_report.ipynb)
- [300-question public BBH subset](data/bbh_300/README.md)
- [300-question fresh dataset](data/study_600/README.md)
- [Original project brief](docs/project-brief.md)

Python 3.11+ is required. Collection, retry handling, scoring and statistical calculations use only the standard library. The notebook uses optional Jupyter, pandas and Matplotlib dependencies.

## Environment and notebook setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-analysis.txt
.\.venv\Scripts\python.exe -m ipykernel install --prefix .venv --name dissent-research --display-name "Dissent Research"
python -m unittest discover -s tests -v
```

These dependencies and the local kernel have already been installed in this checkout. `requirements-analysis.lock.txt` records the tested environment; the ranged requirements file is more portable across Python versions and operating systems.

Put the key and chosen model/provider in `.env`, following `.env.example`. Live commands load it from the current working directory. Process environment variables take precedence; explicit pilot CLI model/provider arguments take precedence over both. `.env` is ignored by Git and never included in manifests or reports.

```powershell
python -m dissent check-config
```

This checks presence and local validity only; it does not authenticate the key or make a model call.

## Data and study plan

The public dataset has 100 examples each from BBH five-object deduction, seven-object deduction, and seven-object tracking. It preserves the original source revision, license, raw files and exact sample membership. Reference labels are automatically scored; they are not claimed to have been independently re-solved or unseen during model training.

The fresh dataset has 100 ordering, 100 Boolean, and 100 shortest-path tasks. Each answer is cross-checked by two exact solvers. Its fresh seed and hashes are frozen in its manifest. Existing 50-question pilot tasks are development data; keep evaluation instances separate from prompt tuning. To create a different frozen evaluation set after development, use a new output directory and update the config before collection:

```powershell
python -m dissent.study prepare --out data/study_600_new
```

Inspect `configs/study.json` before running. Defaults are one homogeneous model team, five agents, three repetition seeds, the nine-condition research suite, and an initial-disagreement selection policy. **600 questions × 5 agents × 3 seeds = 9,000 initial responses.** Use one seed for 3,000 initial responses. Additional model entries create separate homogeneous-team experiments; heterogeneous teams are not implemented.

```powershell
python -m dissent.study plan --config configs/study.json
```

Planning validates data paths, config and local model settings and shows logical call bounds. With three seeds the research-suite bound is 84,600 logical calls before retries; unanimity stopping usually reduces it. The example `max_requests: 90000` is a hard request-attempt limit, including retries across the entire study. The example `$25` `max_reported_cost_usd` is a stop threshold on known usage, **not a guaranteed dollar cap**: it is checked between calls, one call may cross it, and failed-request charges may be unknown. Set an account/key spending cap at the provider if a hard monetary cap is required. The example values are editable planning defaults, not a recommendation to spend that amount.

## Preflight and staged live collection

A preflight creates three new development problems and exercises the configured suite on them. It never uses the evaluation questions. It defaults to a reported-cost stop threshold of at most $1; the same limitations on monetary caps apply. Preflight requires an explicit `--live` for a live backend.

```powershell
python -m dissent.study preflight --config configs/study.json --out runs/preflight-01 --live
```

Three problems test request/response compatibility, not statistical power or difficulty calibration. Inspect errors, token truncation, model/provider resolution, and reviewer blinding before fixing final settings.

Collect independent panels once, inspect their automatically scored categories, then deliberate using those exact cached responses:

```powershell
python -m dissent.study independent --config configs/study.json --out runs/study-01 --live
python -m dissent.study screen --run runs/study-01
python -m dissent.study deliberate --config configs/study.json --out runs/study-01 --live
python -m dissent.study report --run runs/study-01
```

`screen` and `report` make no model calls. Answer keys are only parsed during scoring; selection uses disagreement alone. All initial disagreement cases are retained, including wrong minorities opposing correct majorities. Under `selection: disagreement`, unanimous teams stop and retain their original decision in every condition. Therefore the complete-study accuracy evaluates that stopping policy, not debate applied unconditionally. Use `selection: all` for the latter experiment.

Malformed or failed initial panels remain visible and cannot be classified as correct or wrong minorities. Nonfatal failures in deliberation are recorded, and other questions continue. Global configuration/authentication errors and budget limits halt collection. Final reports distinguish missing results, abstentions and wrong decisions.

## Conditions

| Condition | Additional procedure after the shared initial panel |
|---|---|
| Majority vote | Strict majority of five; no discussion |
| Standard debate | One simultaneous revision round |
| Protected dissent | Closure declarations; qualifying dissent triggers one extra group round |
| Protected dissent + review | Same declarations; qualifying dissent triggers a fresh binding reviewer |
| Independent revision | Each agent revises its original answer without peers |
| Explicit unprotected dissent | Same debate; declaration checkpoint has no escalation power; answers are final votes |
| Original-answer reminder | Same debate; agents revise with their original answers visible, without a dissent mechanism |
| Extra-round control | Neutral checkpoint; an extra group round on the protected branch's escalation events |
| Independent-review control | Neutral checkpoint; fresh reviewer checks the problem/proposal on the same escalation events |

The final two controls are **yoked**: they match protected branches' logical call counts and escalation timing. They do not match tokens exactly, and their scheduling is not an independently deployable policy. This is a mechanism-comparison design, not proof that all other causal differences disappear.

A strict majority needs three matching options. Dissent qualification uses an alternative valid answer, nonempty disputed claim/evidence, and confidence >= 0.6 by default. It never consults correctness. The highest-confidence qualifying dissent is selected with seeded tie breaking; one escalation is allowed. The independent appeal chooses between the proposal, the dissent, and unresolved. Its control reviewer can choose any option or unresolved without seeing dissent. Full details are in the research specification.

## Automatic retries and resume

Each call uses up to four attempts by default (`inference.max_attempts`). Requests are retried for transient connection failures/timeouts and HTTP 408, 409, 425, 429, 500, 502, 503, 504 and 529, including equivalent API error envelopes. A 402 carrying `Retry-After` is treated as a temporary budget wait; ordinary insufficient-credit errors stop.

Backoff is exponential with deterministic jitter. `Retry-After` is respected, including HTTP dates. Server delays longer than 60 seconds are saved as a cooldown and deferred rather than retried early. Every attempt has a timestamp, status, timing, usage if known, and a response if available. Timed-out delivery can be ambiguous and a retry can be charged again; unknown usage is never silently zeroed.

Output allowance starts at 8,192 tokens. An explicit `finish_reason: length` retries only the affected call with twice the allowance, up to `max_tokens_ceiling` (32,768 by default), within the same attempt and spending limits. Each attempt records its actual allowance, response and usage; the next allowance survives a budget pause or explicit retry of an exhausted batch. The base request plus the attempt's `max_tokens` reconstructs the exact request. This fixed recovery policy applies to every condition, never depends on correctness, and does not repeat completed calls. A provider's own output/context limits may require model-specific settings. Reaching the ceiling remains an explicit failure, not a silently accepted partial answer.

Authentication errors, invalid request parameters, refusal and invalid answer/schema outputs are not blindly retried. No correctness-based retries or answer repairs occur. Completed requests are never resent on resume. To allow another bounded batch for an exhausted retryable or interrupted pending call:

```powershell
python -m dissent.study independent --config configs/study.json --out runs/study-01 --live --retry-failed
python -m dissent.study deliberate --config configs/study.json --out runs/study-01 --live --retry-failed
```

Retry failed initial collection before deliberation. Budget-paused calls resume when the operational limit is increased. Limits may change on resume and are recorded for every invocation; datasets, model settings, seeds, selection rules, prompts/source and statistical plan are frozen by the run identity. Invalid-output failures require inspection and a new corrected experimental configuration rather than quietly sampling until an acceptable answer appears. Do not run two writer processes against the same study directory.

## Notebook and reporting

For an Anaconda workflow, open `notebooks/run_experiment.ipynb` and follow its setup instructions. Its default six-question mock demo makes no API calls. Select your Anaconda kernel, run cells in order, and change the mode and live opt-in only when ready for paid collection. The notebook uses the same collection, persistence, retry and reporting code as the CLI. Its source is maintained in `scripts/build_experiment_notebook.py`; rebuild the reporting notebook first when changing shared analysis cells.

```powershell
$env:DISSENT_STUDY_DIR = (Resolve-Path runs/study-01).Path
.\.venv\Scripts\python.exe -m jupyterlab notebooks/research_report.ipynb
```

Select the **Dissent Research** kernel and run all cells. The notebook does not read `.env` or initiate collection. It produces integrity checks, screening tables, missingness/coverage, accuracy and minority outcomes by source/family/model, panel transitions, paired comparisons with question-cluster bootstrap intervals, exact McNemar or cluster sign-flip tests, Holm-adjusted p-values, resource summaries, PNG/PDF figures, CSV tables and an audit sample. Repeated seeds are clustered by question. Empty strata remain undefined.

For reproducible headless execution:

```powershell
.\.venv\Scripts\python.exe scripts/execute_notebook.py --run runs/study-01
```

Run the full workflow offline using a small fixture with two data sources, two model labels, and two seeds:

```powershell
python scripts/smoke_study.py --out runs/study-verified
.\.venv\Scripts\python.exe scripts/execute_notebook.py --run runs/study-verified
```

The already verified fixture is in `runs/study-verified`. Use `--out runs/study-smoke-new` for another fixture run. Mock behavior is a software fixture with zero token charges; it does not simulate model quality or supply research evidence.

## Audit files

The study directory contains an immutable identity and task snapshot, per-model/seed units, per-question trajectories, per-call attempt journals, `screening.jsonl`, `analysis_rows.jsonl`, `research_summary.json`, and `research_report.md`. Notebook execution adds `tables/`, `figures/`, package versions, and an executed `.ipynb`. Gold keys stay in separate dataset files. Physical accounting counts shared requests once; standalone protocol costs include each protocol's full path. Request latency sums exclude retry backoff; attempt timestamps and study timestamps retain elapsed scheduling history.

## Scope

This implements the proposed hybrid study workflow and its principal controls. Controlled majority-pressure construction, heterogeneous teams, dissent-representation ablations, arbitrary free-response maths scoring, and calibrated power analysis remain research extensions. The example statistical plan is explicit and frozen on collection; it is not externally preregistered or a guarantee of sufficient power. Reviewer filtering is heuristic, so audit the actual arguments for residual social cues. Conference readiness still depends on the live results and defensible interpretation.

The original four-condition pilot CLI remains available (`python -m dissent run`, `python -m dissent analyze`). New source versions require new run directories; old pilot outputs remain readable but cannot be resumed under changed source/config hashes.
