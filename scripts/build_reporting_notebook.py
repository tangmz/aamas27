"""Build the checked-in, unexecuted reporting notebook from explicit cell sources."""
import json
from pathlib import Path

cells=[]
def md(text): cells.append({'cell_type':'markdown','metadata':{},'source':text.strip().splitlines(keepends=True)})
def code(text): cells.append({'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':text.strip().splitlines(keepends=True)})

md('''# Protected dissent: statistical reporting

This notebook **only reads and analyses saved study data**. It does not load API credentials or call a model. Set `RUN_DIR` below to your study directory. The default is the offline smoke study; synthetic results are visibly labelled and must not be used as empirical findings.

The paired experimental unit is a question. Repeated seeds remain together in question-cluster inference. The primary estimates compare complete paired outcomes; failed and missing outcomes are reported separately. Read `docs/research-workflow.md` before interpreting results.''')
code('''from pathlib import Path
import os, sys, json, importlib.metadata, io
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'dissent').is_dir())
sys.path.insert(0, str(ROOT))
RUN_DIR = Path(os.environ.get('DISSENT_STUDY_DIR', str(ROOT / 'runs/study-verified'))).resolve()
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from IPython.display import display, Markdown, Image
from dissent.reporting import write_study_report
from dissent.common import read_jsonl, write_json

FIGURES = RUN_DIR / 'figures'
EXPORTS = RUN_DIR / 'tables'
FIGURES.mkdir(parents=True, exist_ok=True)
EXPORTS.mkdir(parents=True, exist_ok=True)
pd.set_option('display.max_colwidth', 65)
pd.set_option('display.max_rows', 100)
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
def show(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=120, bbox_inches='tight')
    display(Image(data=buffer.getvalue()))''')
md('''## Integrity and collection status

The reporting loader checks task and answer-key hashes, task IDs, option labels, panel sizes, and successful call references. A failed collection is not silently converted into an incorrect answer. `success_over_scheduled` deliberately treats unavailable decisions as unsuccessful operational outcomes; complete-case accuracy uses only available decisions.''')
code('''report = write_study_report(RUN_DIR)
rows = pd.DataFrame(read_jsonl(RUN_DIR / 'analysis_rows.jsonl'))
screen = pd.DataFrame(read_jsonl(RUN_DIR / 'screening.jsonl'))
summary = pd.DataFrame(report['descriptive'])
contrasts = pd.DataFrame(report['contrasts'])
resources = pd.DataFrame(report['resources'])
BANNER = 'SYNTHETIC SOFTWARE TEST' if report['synthetic'] else 'LIVE EXPERIMENT'
display(Markdown(f'**{BANNER}** — collection status: `{report["study_status"]}`'))
display(rows.groupby(['model_id', 'collection_status'], dropna=False)['task_id'].count().rename('protocol_rows').to_frame())
versions = {name: importlib.metadata.version(name) for name in ('numpy', 'pandas', 'matplotlib', 'nbformat', 'nbclient')}
write_json(RUN_DIR / 'analysis_environment.json', {'python':sys.version, 'packages':versions})
print('Questions:', screen.task_id.nunique(), '| model/seed panels:', len(screen), '| protocol rows:', len(rows))''')
md('''## Initial disagreement and screening

Selection uses initial disagreement, not ground truth. The configured policy stops unanimous panels and deliberates on all disagreeing panels, including majority-correct/minority-wrong cases. The table distinguishes no strict majority from majority-wrong/minority-correct. Repeated panels are not independent questions.''')
code('''screening_table = screen.groupby(['model_id', 'dataset', 'initial_category'], dropna=False).agg(panels=('task_id','size'), unique_questions=('task_id','nunique')).reset_index()
display(screening_table)
display(screen.groupby(['model_id','dataset'], dropna=False).agg(planned_panels=('task_id','size'), observed_panels=('initial_available','sum'), selected_panels=('selected','sum')))
screening_table.to_csv(EXPORTS / 'screening.csv', index=False)''')
md('''## Accuracy, coverage and failure rates

Report public and fresh datasets separately. Overall accuracy reflects the configured unanimity-stop policy if selection is `disagreement`. It is not an estimate of unconditional debate applied to every question. Source/family rows are descriptive; inspect available and scheduled denominators.''')
code('''display(summary[['model_id','scope','protocol','available_panels','scheduled_panels','missing_panels','success_over_scheduled','accuracy_complete_cases','coverage_over_scheduled','accuracy_when_resolved']])
for model in summary.model_id.unique():
    table = summary[(summary.model_id == model) & (summary.scope == 'all')]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    labels = table.protocol.str.replace('_',' ')
    for ax, field, title in zip(axes, ['success_over_scheduled','coverage_over_scheduled'], ['Correct decisions / scheduled panels','Resolved decisions / scheduled panels']):
        ax.barh(labels, table[field], color='#247B8C')
        ax.set_xlim(0,1)
        ax.set_title(title)
        ax.set_xlabel('Proportion')
    axes[0].invert_yaxis()
    fig.suptitle(f'{BANNER} | {model}')
    fig.tight_layout()
    fig.savefig(FIGURES / f'{model}_accuracy_coverage.png', dpi=180, bbox_inches='tight')
    fig.savefig(FIGURES / f'{model}_accuracy_coverage.pdf', bbox_inches='tight')
    show(fig)
    plt.close(fig)''')
md('''## Correct-minority outcomes

Recovery means a correct final decision on an initially majority-wrong/minority-correct panel. Suppression requires a unanimous wrong final panel agreeing with the wrong final decision. A wrong majority alone is not suppression. An independent appeal can repair the decision without repairing any panel member's answer. Empty focus strata are undefined, not zero.''')
code('''focus_table = summary[['model_id','scope','protocol','focus_scheduled','focus_available','minority_recovery','minority_suppression','minority_agent_survival','false_dissent','false_qualifying_dissent','escalation_rate']]
display(focus_table)
for model in summary.model_id.unique():
    table = summary[(summary.model_id == model) & (summary.scope == 'all')]
    fig, axes = plt.subplots(1,2,figsize=(14,6),sharey=True)
    for ax, field, title in zip(axes,['minority_recovery','minority_suppression'],['Recovery (higher is better)','Suppression (lower is better)']):
        values = pd.to_numeric(table[field], errors='coerce')
        ax.barh(table.protocol.str.replace('_',' '),values,color='#72569A')
        ax.set_xlim(0,1)
        ax.set_title(title)
        for i, value in enumerate(values):
            if pd.isna(value): ax.text(0.02,i,'N/A: empty focus stratum',va='center')
    axes[0].invert_yaxis()
    fig.suptitle(f'{BANNER} | {model} | conditional on initial correct minority')
    fig.tight_layout()
    fig.savefig(FIGURES / f'{model}_minority_outcomes.png',dpi=180,bbox_inches='tight')
    show(fig)
    plt.close(fig)''')
md('''## Planned paired comparisons

Effects are treatment minus baseline. Positive values favor treatment for accuracy/recovery; negative values favor treatment for suppression. Percentile bootstrap intervals resample questions within source/family strata, carrying all repetitions of each question together. Exact McNemar tests apply when each question contributes once. Repeated panels use question-cluster sign flips, which assume paired exchangeability under the null.

Holm adjustment covers all planned endpoint/source-scope comparisons within each model. These intervals are marginal, not simultaneous. Cross-model significance claims need a broader correction plan. These observational protocol contrasts and small pilot samples warrant cautious interpretation; a low p-value alone does not isolate a social mechanism.''')
code('''display(contrasts[['model_id','scope','endpoint','treatment','baseline','n_questions','n_pairs','missing_pairs','difference','bootstrap_95','test','p_value','p_holm','bootstrap_degenerate']])
for model in contrasts.model_id.unique():
    table = contrasts[(contrasts.model_id == model) & (contrasts.scope == 'all') & (contrasts.endpoint == 'accuracy')].copy()
    table = table[table.bootstrap_95.map(lambda value: isinstance(value,list))]
    if table.empty:
        print(f'{model}: not enough paired questions for intervals')
        continue
    fig, ax = plt.subplots(figsize=(12, max(4, len(table)*0.6)))
    for position, (_, row) in enumerate(table.iterrows()):
        low, high = row.bootstrap_95
        ax.plot([100*low,100*high],[position,position],color='#247B8C',linewidth=2)
        ax.plot(100*row.difference,position,'o',color='#163B45')
    ax.set_yticks(range(len(table)), [a.replace('_',' ')+' vs '+b.replace('_',' ') for a,b in zip(table.treatment,table.baseline)])
    ax.axvline(0,color='grey',linestyle='--')
    ax.set_xlabel('Accuracy difference (percentage points); question-cluster 95% intervals')
    ax.invert_yaxis()
    ax.set_title(f'{BANNER} | {model}')
    fig.tight_layout()
    fig.savefig(FIGURES / f'{model}_paired_effects.png',dpi=180,bbox_inches='tight')
    fig.savefig(FIGURES / f'{model}_paired_effects.pdf',bbox_inches='tight')
    show(fig)
    plt.close(fig)''')
md('''## Agent transitions and resource trade-offs

Transition counts describe panel members; do not use agents as independent statistical samples. The two yoked controls match logical call counts to the protected branches on the same escalation events. They do not match prompt/output tokens. Physical costs count shared prefixes once, while standalone costs allocate each protocol its full path. Unknown retry charges remain missing; a reported-cost threshold is not a guaranteed dollar cap.''')
code('''display(summary[summary.scope == 'all'][['model_id','protocol','correct_to_correct','correct_to_wrong','wrong_to_correct','wrong_to_wrong','mean_calls','mean_request_attempts','mean_tokens','mean_cost_usd','mean_latency_seconds']])
display(resources)
for model in summary.model_id.unique():
    table = summary[(summary.model_id == model) & (summary.scope == 'all')]
    fig, ax = plt.subplots(figsize=(12,6))
    markers = ['o','s','^','D','v','P','X','*','h']
    for i, (_, row) in enumerate(table.iterrows()):
        if pd.notna(row.mean_calls):
            ax.scatter(row.mean_calls,row.success_over_scheduled,s=65,marker=markers[i % len(markers)],label=row.protocol.replace('_',' '),alpha=0.8)
    ax.legend(loc='center left',bbox_to_anchor=(1.02,0.5),fontsize=8)
    ax.set_xlabel('Mean standalone logical calls per available panel')
    ax.set_ylabel('Correct decisions / scheduled panels')
    ax.set_ylim(-0.02,1.05)
    ax.set_title(f'{BANNER} | {model} | inspect token/cost table alongside call counts')
    fig.tight_layout()
    fig.savefig(FIGURES / f'{model}_cost_accuracy.png',dpi=180,bbox_inches='tight')
    show(fig)
    plt.close(fig)''')
md('''## Audit sample and exports

This stratified sample is for qualitative inspection, not estimating population rates. Use its task IDs to inspect the saved initial responses, debate, dissent, and reviewer inputs. Inspect natural-language social cues in reviewer arguments: lexical filtering does not prove perfect blinding.

CSV exports contain derived analysis data, not credentials. Record any annotation corrections separately and rerun the analysis with disclosed changes.''')
code('''audit_sample = (screen.sort_values(['model_id','dataset','task_id','seed']).groupby(['model_id','dataset','initial_category'], group_keys=False).head(2))
display(audit_sample[['model_id','dataset','seed','task_id','initial_category','initial_answers','correct_answer']])
summary.to_csv(EXPORTS / 'descriptive.csv',index=False)
contrasts.to_csv(EXPORTS / 'paired_comparisons.csv',index=False)
resources.to_csv(EXPORTS / 'resources.csv',index=False)
audit_sample.to_csv(EXPORTS / 'manual_audit_sample.csv',index=False)
rows.to_csv(EXPORTS / 'analysis_rows.csv',index=False)
print('Saved tables to',EXPORTS)
print('Saved figures to',FIGURES)
print('Statistical plan:',json.dumps(report['identity']['statistics'],indent=2))''')
md('''## Interpretation checklist

- Report unique questions, model/seed panels, missingness, coverage and focus-stratum size.
- Compare protected dissent with both ordinary debate and matched-call controls.
- Report outcomes on majority-correct teams as well as correct minorities; dissent may harm good decisions.
- Keep public and fresh results separate; do not claim public questions were unseen in training.
- Do not tune prompts or change sample selection after examining evaluation effects.
- A three-question preflight validates API behavior, not power, model calibration, or conference readiness.
- Treat empty strata, very small numbers of questions, and degenerate intervals as limitations.

Method references: [SciPy binomial-test documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html) and [paired bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html). The repository implementation uses its own tested standard-library routines; the cluster and multiplicity choices are specified in `docs/research-workflow.md`.''')
for i,cell in enumerate(cells): cell['id']=f'cell-{i:02d}'
notebook={'cells':cells,'metadata':{'kernelspec':{'display_name':'Dissent Research','language':'python','name':'dissent-research'},'language_info':{'name':'python','version':'3.11'}},'nbformat':4,'nbformat_minor':5}
root=Path(__file__).resolve().parents[1]
(root/'notebooks/research_report.ipynb').write_text(json.dumps(notebook,indent=2)+'\n',encoding='utf-8')
print('Wrote',len(cells),'notebook cells')
