"""Offline integration fixture: two data sources, two model labels, two seeds."""
import argparse
import contextlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dissent.common import load_tasks, read_jsonl, write_json, write_jsonl
from dissent.study import execute_study
from dissent.reporting import write_study_report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'runs/study-smoke')
    args=parser.parse_args()
    out=args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a fresh smoke-study output directory')
    inputs=out.parent/(out.name+'-inputs')
    datasets=[]
    for label, source in [('bbh',ROOT/'data/bbh_300'),('fresh',ROOT/'data/study_600/fresh')]:
        all_tasks=load_tasks(source/'tasks.jsonl')
        families={}
        for task in all_tasks:
            families.setdefault(task['family'],[]).append(task)
        tasks=[t for group in families.values() for t in group[:2]]
        ids={t['task_id'] for t in tasks}
        gold=[row for row in read_jsonl(source/'answers.jsonl') if row['task_id'] in ids]
        write_jsonl(inputs/label/'tasks.jsonl',tasks)
        write_jsonl(inputs/label/'answers.jsonl',gold)
        datasets.append({'id':label,'tasks':f'{label}/tasks.jsonl','answers':f'{label}/answers.jsonl'})
    spec=json.loads((ROOT/'configs/study.json').read_text())
    spec.update(name='offline-software-fixture',datasets=datasets,
                models=[{'id':name,'backend':'mock','model':'mock-fixture-v1','provider':'offline'} for name in ['fixture_a','fixture_b']],
                seeds=[2027,2028],limits={'max_requests':4000,'max_reported_cost_usd':1})
    spec['statistics']['bootstrap_samples']=400
    write_json(inputs/'config.json',spec)
    inputs.mkdir(parents=True,exist_ok=True)
    print('Running offline two-stage study; detailed progress in',inputs/'execution.log',flush=True)
    with (inputs/'execution.log').open('w',encoding='utf-8') as log, contextlib.redirect_stdout(log):
        execute_study(inputs/'config.json',out,'independent')
        write_study_report(out,screen_only=True)
        execute_study(inputs/'config.json',out,'deliberate')
        report=write_study_report(out)
    print('Completed:',len(report['descriptive']),'descriptive rows;',len(report['contrasts']),'contrasts;',sum(x['request_attempts'] for x in report['resources']),'mock attempts')
    print('No live model requests were made.')


if __name__=='__main__': main()
