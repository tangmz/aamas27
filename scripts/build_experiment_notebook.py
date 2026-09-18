"""Build an Anaconda-compatible collection and inline reporting notebook."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cells = []


def md(source):
    cells.append(dict(cell_type="markdown", metadata={}, source=source.strip()))


def code(source):
    cells.append(dict(cell_type="code", metadata={}, source=source.strip(), execution_count=None, outputs=[]))


md('''# Run the protected-dissent experiment

Run this notebook from top to bottom with **Shift+Enter**. Progress appears below the collection cells; responses are saved to disk as requests finish. Tables and figures appear after collection. The default is a small **offline software demo**, not research evidence.

## Anaconda setup (once)
In **Anaconda Prompt**, run:
```bat
cd C:\\Users\\MingZeTang\\Documents\\GitHub\\aamas27
conda create -n dissent-research python=3.11 -y
conda activate dissent-research
python -m pip install -r requirements-analysis.txt
python -m ipykernel install --user --name dissent-conda --display-name "Dissent Research (Anaconda)"
python -m jupyterlab notebooks/run_experiment.ipynb
```
Select **Dissent Research (Anaconda)** as the notebook kernel. Alternatively, open JupyterLab through Anaconda Navigator in that environment. This notebook uses your selected kernel's Python, not the repository's `.venv`.

Keep credentials in the repository's `.env`; do not paste or display keys in cells. No installation or paid requests happen merely by opening this notebook.''')
code('''from pathlib import Path
import os, sys, json
from IPython.display import display, Markdown

# If Jupyter starts elsewhere, replace None with the absolute repository path.
PROJECT_ROOT = None
if PROJECT_ROOT is None:
    ROOT = next((p for p in [Path.cwd(), *Path.cwd().parents]
                 if (p / 'dissent' / 'study.py').is_file()), None)
    if ROOT is None:
        raise RuntimeError('Set PROJECT_ROOT to your aamas27 repository path above.')
else:
    ROOT = Path(PROJECT_ROOT).expanduser().resolve()
    if not (ROOT / 'dissent' / 'study.py').is_file():
        raise RuntimeError('PROJECT_ROOT does not contain dissent/study.py')
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
print('Python:', sys.executable)
print('Repository:', ROOT)
if sys.version_info < (3, 11):
    raise RuntimeError('Use Python 3.11 or newer.')
import pandas as pd
import matplotlib
import nbformat, nbclient
from dissent.common import write_json, read_jsonl
from dissent.tasks import save_dataset
from dissent.environment import load_env
from dissent.study import resolve_plan, execute_study, preflight
from dissent.reporting import write_study_report''')
md('''## Choose the run

- `demo`: six generated questions, mock responses, one repetition; no API charges.
- `preflight`: three new development questions with your configured live model(s), first repetition, all conditions. This checks compatibility, not statistical power.
- `study`: the full settings in `configs/study.json`, currently 600 questions and three repetitions (9,000 independent responses plus deliberation).

For either live mode, deliberately set `ALLOW_LIVE = True`. Check the model/provider and budgets in the config first. Reported-cost thresholds are not hard monetary caps. Preflight limits known reported cost to at most $1.

The study config now starts at 8,192 output tokens. Explicit truncation automatically retries only that call at 16,384 and then 32,768 tokens, subject to attempt/spending limits and provider support. Every attempt is saved. Completed calls in the same run are reused. Older preflight runs used the original policy: keep them as development records and use a new run name with this updated code.

Choose a different `RUN_NAME` for each new experiment. To resume a study, keep its name and settings unchanged. Do not run two notebooks/processes writing to the same directory. Do not tune prompts on evaluation results.''')
code('''MODE = 'demo'                 # 'demo', 'preflight', or 'study'
ALLOW_LIVE = False             # True authorizes paid calls in this notebook
RUN_NAME = 'notebook-demo-02'  # Change for a new run
RETRY_FAILED = False          # Another bounded retry batch for transient failures

if MODE not in {'demo', 'preflight', 'study'}:
    raise ValueError('Unknown MODE')
if not RUN_NAME or Path(RUN_NAME).name != RUN_NAME or RUN_NAME in {'.', '..'}:
    raise ValueError('RUN_NAME must be a single directory name')
if MODE != 'demo' and not ALLOW_LIVE:
    raise RuntimeError('Review the live settings, then set ALLOW_LIVE=True.')
BASE_CONFIG = ROOT / 'configs/study.json'
RUN_BASE = ROOT / 'runs' / RUN_NAME
RUN_DIR = RUN_BASE / 'run' if MODE == 'preflight' else RUN_BASE
CONFIG = BASE_CONFIG

if MODE == 'demo':
    inputs = ROOT / 'runs' / (RUN_NAME + '-inputs')
    CONFIG = inputs / 'config.json'
    if not CONFIG.exists():
        save_dataset(inputs / 'development', 6, 73491)
        spec = json.loads(BASE_CONFIG.read_text(encoding='utf-8'))
        spec.update(name='notebook-offline-demo',
                    datasets=[{'id': 'development', 'tasks': 'development/tasks.jsonl',
                               'answers': 'development/answers.jsonl'}],
                    models=[{'id': 'fixture', 'backend': 'mock',
                             'model': 'mock-fixture-v1', 'provider': 'offline'}],
                    seeds=[2027], selection='all',
                    limits={'max_requests': 1000, 'max_reported_cost_usd': 1.0})
        spec['statistics']['bootstrap_samples'] = 200
        write_json(CONFIG, spec)
else:
    load_env()

spec, identity, tasks = resolve_plan(CONFIG)
if MODE == 'demo' and any(m['backend'] != 'mock' for m in identity['models']):
    raise RuntimeError('Demo config must contain only mock models.')
panels = len(tasks) * len(identity['models']) * len(identity['seeds'])
display(Markdown('**SYNTHETIC SOFTWARE DEMO**' if MODE == 'demo' else '**PAID LIVE RUN**'))
print('Output directory:', RUN_DIR)
display(pd.DataFrame(identity['models']))
print('Base plan:', len(tasks), 'questions;', panels, 'panels;', 5 * panels, 'initial calls')
print('Limits:', spec['limits'])
if MODE == 'preflight':
    print('Preflight replaces the base dataset with 3 new questions and uses only the first seed.')''')
md('''## Collect independent answers (or run the complete preflight)

This cell runs synchronously: wait for it to finish before running the next cell. Each progress line reports a completed/attempted question, not each individual HTTP request. Network timeouts and retry backoff can make a line take time. Request journals are written during collection.

Use **Kernel → Interrupt** to stop collection; completed calls remain saved. For a study/demo, rerun this cell to resume. Set `RETRY_FAILED=True` only when another bounded batch of transient/ambiguous failures is intended. Permanent configuration errors need correction; changed experimental settings require a new run directory.

Preflight requires a fresh directory. If a preflight is interrupted, follow the resume instructions at the end rather than regenerating its questions.''')
code('''if MODE == 'preflight':
    if (RUN_DIR / 'research_summary.json').exists():
        print('Using completed preflight. Choose a new RUN_NAME to repeat it.')
    else:
        preflight(BASE_CONFIG, RUN_BASE, live=ALLOW_LIVE)
else:
    execute_study(CONFIG, RUN_DIR, 'independent', live=ALLOW_LIVE,
                  retry_failed=RETRY_FAILED)
print('Saved responses in:', RUN_DIR / 'units')''')
md('''## Inspect initial disagreement
Classification is automatic. Gold labels are used here for scoring, never for deciding which panels receive deliberation.''')
code('''write_study_report(RUN_DIR, screen_only=True)
screening = pd.DataFrame(read_jsonl(RUN_DIR / 'screening.jsonl'))
display(screening.groupby(['model_id', 'dataset', 'initial_category'], dropna=False)
        .size().rename('panels').reset_index())
display(screening.head(10))''')
md('''## Run deliberation and comparison conditions
This reuses the saved independent responses. Successful requests are cached; transient failures use the existing retry policy. Preflight already completed this step.''')
code('''if MODE != 'preflight':
    execute_study(CONFIG, RUN_DIR, 'deliberate', live=ALLOW_LIVE,
                  retry_failed=RETRY_FAILED)
else:
    print('Deliberation was included in preflight.')
os.environ['DISSENT_STUDY_DIR'] = str(RUN_DIR)
print('Collection finished. Continue for inline statistical results.')''')
md('''## Results, plots, and response audit
The remaining cells reuse the analysis notebook's reporting code. They make no model calls. Demo/preflight samples are too small for research conclusions. Missing results and empty minority strata remain visible; repeated seeds are clustered by question.''')
# Embed the existing reporting cells to keep statistical definitions identical.
report = json.loads((ROOT / 'notebooks/research_report.ipynb').read_text(encoding='utf-8'))
cells.extend(copy_cell for copy_cell in report['cells'][1:])
md('''## Inspect a saved response
Change `CALL_INDEX` and rerun this cell to inspect a different saved call. The structured response includes the returned answer and explanation, not hidden internal reasoning. The journal path contains the full request, returned API response, and attempt history. Failed calls may have no parsed response.''')
code('''CALL_INDEX = 0
call_files = sorted((RUN_DIR / 'units').glob('*/calls/*.json'))
if not call_files:
    print('No call journals found.')
elif not 0 <= CALL_INDEX < len(call_files):
    print('Choose CALL_INDEX from 0 to', len(call_files) - 1)
else:
    path = call_files[CALL_INDEX]
    journal = json.loads(path.read_text(encoding='utf-8'))
    print('Journal:', path)
    print('Call:', journal.get('call_id'), '| Status:', journal.get('status'))
    print('Attempts:', len(journal.get('attempts', [])))
    print(json.dumps(journal.get('parsed', {'note': 'No valid structured response'}),
                     indent=2, ensure_ascii=False))''')
md('''## Save and resume

Save this notebook with **Ctrl+S** to retain its displayed output. Raw calls and results are already saved under `RUN_DIR`; tables and figures are exported there too. `runs/` is ignored by Git: back it up separately with the frozen code, configuration and datasets, excluding `.env`.

For an interrupted preflight only, set `CONFIG = RUN_BASE / 'config.json'` and call:
```python
execute_study(CONFIG, RUN_DIR, 'independent', live=True, retry_failed=True)
execute_study(CONFIG, RUN_DIR, 'deliberate', live=True, retry_failed=True)
os.environ['DISSENT_STUDY_DIR'] = str(RUN_DIR)
```
Then rerun the result cells. This reuses its saved development questions. Do not regenerate them in the same directory. If you restart the kernel, run setup/settings first; do not execute the preflight collection cell again for an interrupted run.

For a partial study after interrupting deliberation, you may run the analysis cells with `DISSENT_STUDY_DIR` set to that run. Interpret their missing-result denominators; partial results are not the final study.''')
for i, cell in enumerate(cells):
    cell['id'] = f'experiment-{i:03d}'
    if cell['cell_type'] == 'code':
        cell.update(execution_count=None, outputs=[])
notebook = dict(cells=cells, metadata={
    'kernelspec': {'display_name': 'Python 3 (ipykernel)', 'language': 'python', 'name': 'python3'},
    'language_info': {'name': 'python', 'version': '3.11'}}, nbformat=4, nbformat_minor=5)
output = ROOT / 'notebooks/run_experiment.ipynb'
output.write_text(json.dumps(notebook, indent=1) + '\n', encoding='utf-8')
print(output)
