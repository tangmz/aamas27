"""Create an offline notebook for inspecting recovery artifacts and protocol traces."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cells = []


def md(text):
    cells.append({'cell_type':'markdown','metadata':{},'source':text})


def code(text):
    cells.append({'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':text})


md('''# Research recovery: evidence and persistent challenges
This notebook makes **no API calls** and does not read `.env`. It inspects the saved recovery pack and demonstrates procedural rules. It contains no new efficacy results. The target is a Blue Sky vision draft, subject to author/supervisor review.

Read `docs/recovery-plan.md` and `paper/blue-sky/main.pdf`. Existing study results remain unchanged. All scenario counts below are hypothetical assignments to two archived arguments, not observed five-agent votes.''')
code('''from pathlib import Path
import json, sys
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p/'recovery').is_dir())
sys.path.insert(0, str(ROOT))
import pandas as pd
from IPython.display import display, Markdown
from dissent.common import read_jsonl
from recovery.standing import Ledger, verify_finite_examples
PACK = ROOT/'runs/recovery-01'
summary = json.loads((PACK/'audit_summary.json').read_text(encoding='utf-8'))
cases = read_jsonl(PACK/'public_cases.jsonl')
reviews = read_jsonl(PACK/'manual_review.jsonl')
display(pd.Series(summary['screening'], name='initial_panels').to_frame())
display(pd.Series(summary['candidate_families'], name='reusable_questions').to_frame())
print('Split by question:', summary['split_questions'])
print('Known source cost (incomplete accounting):', summary['known_source_cost_usd'])''')
md('''## Inspect a development argument pair
These arguments require author review for coherence, ambiguity and accidental social cues. Correct answers are intentionally omitted here. Do not choose items based on the result of a later treatment comparison.''')
code('''development = [r for r in reviews if r['split']=='development']
PAIR_INDEX = 0
pair = development[PAIR_INDEX]
print('Question:', pair['task_id'], '| review status:', pair['review_status'])
case = next(c for c in cases if c['task_id']==pair['task_id'])
print(case['problem']['question'])
display(pd.DataFrame(pair['arguments']))
display(pd.DataFrame([{'case_id':c['case_id'], 'support_counts':c['hypothetical_support_counts']}
                      for c in cases if c['task_id']==pair['task_id']]))''')
md('''## Demonstrate the protocol, without simulating model quality
A changed answer does not erase the objection. A review or an explicit unresolved disposition is required. This verifies controller behaviour only.''')
code('''ledger = Ledger(capacity=1)
ledger.register('objection-1', 'agent-1', 'A', 'A specific constraint may be violated.')
ledger.change_endorsement('agent-1', 'B')
print('Status after changing answer:', ledger.challenges['objection-1'].status)
try:
    ledger.close('B')
except ValueError as error:
    print('Closure blocked:', error)
ledger.expire()
print('Closure after deadline:', ledger.close('B'))
display(verify_finite_examples())''')
md('''## Costs and remaining scientific work
The arithmetic below applies historical per-attempt costs to a different proposed workload. It is neither a price quote nor a spending cap. No requests are dispatched by this notebook. Manual review, the supervisor's novelty assessment, and a development check remain prerequisites for any paid extension.''')
code('''display(pd.Series(summary['illustrative_budget'], name='planning_value').to_frame())
display(Markdown('**Not yet established:** accuracy benefit, review reliability, novelty against all institutional dialogue work, or adequate statistical power.'))''')
for i,c in enumerate(cells):c['id']=f'recovery-{i}'
nb={'cells':cells,'metadata':{'kernelspec':{'name':'python3','language':'python','display_name':'Python 3 (ipykernel)'}},'nbformat':4,'nbformat_minor':5}
(root/'notebooks/recovery_review.ipynb').write_text(json.dumps(nb,indent=2)+'\n',encoding='utf-8')
