"""Build a reproducible, offline argument-replay candidate pack from saved calls.

No network access or model calls. Gold is used for explicit benchmark enrichment,
never exported inside public stimuli. This is a post hoc diagnostic population.
"""
import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

from dissent.common import digest, read_jsonl, seed_for, write_json, write_jsonl
from dissent.reporting import materialize
from dissent.study import gold_for


def build(run, out):
    run, out = Path(run).resolve(), Path(out).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a new output directory; existing audit artifacts are immutable')
    manifest, rows, screening, resources = materialize(run)
    gold = gold_for(manifest['identity'])
    tasks = {t['task_id']: t for t in read_jsonl(run / 'tasks.jsonl')}
    candidates = defaultdict(list)
    costs, token_counts, journal_hashes = [], [], {}
    errors, finishes = Counter(), Counter()
    for path in sorted((run / 'units').glob('*/calls/*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        rel = path.relative_to(run).as_posix()
        journal_hashes[rel] = digest(record)
        for attempt in record['attempts']:
            usage = attempt.get('usage', {})
            if isinstance(usage.get('cost'), (int, float)):
                costs.append(usage['cost'])
            if isinstance(usage.get('total_tokens'), (int, float)):
                token_counts.append(usage['total_tokens'])
            for choice in attempt.get('response', {}).get('choices', []):
                finishes[choice.get('finish_reason')] += 1
        if record['status'] != 'ok':
            errors[record.get('error_type', record['status'])] += 1
        if record['kind'] != 'independent' or record['status'] != 'ok':
            continue
        task_id = record['call_id'].rsplit('/', 2)[0]
        candidates[task_id].append({
            'answer': record['parsed']['answer'], 'reasoning': record['parsed']['reasoning'],
            'source_journal': rel, 'source_call_id': record['call_id'],
            'source_sha256': digest(record),
        })
    pairs = []
    for task_id, records in sorted(candidates.items()):
        correct = [r for r in records if r['answer'] == gold[task_id]]
        wrong = [r for r in records if r['answer'] != gold[task_id]]
        if not correct or not wrong:
            continue
        # Fixed content-independent provenance ranking; no quality/outcome cherry-picking.
        key = lambda r: digest([r['source_journal'], r['source_call_id']])
        pair = [min(correct, key=key), min(wrong, key=key)]
        random.Random(seed_for('replay-pair-order-v1', task_id)).shuffle(pair)
        pairs.append({'task_id': task_id, 'family': tasks[task_id]['family'], 'arguments': pair})
    # Whole questions stay in one split. Stratify the post hoc pool by task family.
    by_family = defaultdict(list)
    for pair in pairs:
        by_family[pair['family']].append(pair)
    development = set()
    for group in by_family.values():
        ordered = sorted(group, key=lambda p: digest(['replay-split-v1', p['task_id']]))
        development.update(p['task_id'] for p in ordered[:max(1, len(ordered) // 5)])
    public, keys, provenance, review = [], [], [], []
    for pair in pairs:
        tid = pair['task_id']
        split = 'development' if tid in development else 'evaluation'
        arguments = [{k: r[k] for k in ('answer', 'reasoning')} for r in pair['arguments']]
        review.append({'task_id': tid, 'split': split, 'review_status': 'pending',
                       'ambiguity': None, 'social_cues': None, 'reasoning_quality': None,
                       'notes': '', 'arguments': arguments})
        for orientation in (0, 1):
            case_id = digest(['support-swap-v1', tid, orientation])[:20]
            support = [4, 1] if orientation == 0 else [1, 4]
            public.append({'case_id': case_id, 'task_id': tid, 'split': split,
                           'problem': tasks[tid], 'arguments': arguments,
                           'hypothetical_support_counts': support,
                           'construction': 'Two fixed archived arguments; assigned support counts, not observed votes.'})
            majority = arguments[support.index(4)]['answer']
            keys.append({'case_id': case_id, 'task_id': tid, 'correct_answer': gold[tid],
                         'majority_correct': majority == gold[tid]})
        provenance.append({'task_id': tid, 'split': split, 'sources': pair['arguments']})
    summary = {
        'source_manifest_sha256': digest(manifest), 'source_journals_sha256': digest(journal_hashes),
        'status': 'offline_candidates_only_not_an_efficacy_experiment',
        'screening': dict(Counter(r['initial_category'] for r in screening)),
        'questions': len(tasks), 'panels': len(screening),
        'reusable_questions': len(pairs), 'candidate_cases': len(public),
        'candidate_families': dict(Counter(p['family'] for p in pairs)),
        'split_questions': dict(Counter(p['split'] for p in provenance)),
        'initial_valid_wrong_responses': sum(r['answer'] != gold[t] for t, rs in candidates.items() for r in rs),
        'known_source_cost_usd': sum(r['cost_known_subtotal'] for r in resources),
        'source_request_attempts': sum(r['request_attempts'] for r in resources),
        'source_cost_missing_calls': sum(r['cost_missing_calls'] for r in resources),
        'finish_reasons': dict(finishes), 'terminal_errors': dict(errors),
        'public_sha256': digest(public), 'keys_sha256': digest(keys),
        'limitations': ['post hoc selected on observed answer disagreement',
                       'same problem family and model as study-01; not independent replication',
                       'assigned support is hypothetical; no duplicated argument text',
                       'manual argument-quality audit pending',
                       'new model responses required to estimate treatment effects'],
    }
    average = sum(costs) / len(costs) if costs else None
    sorted_costs = sorted(costs)
    p95 = sorted_costs[math.ceil(.95 * len(costs))-1] if costs else None
    summary['illustrative_budget'] = {
        'new_calls_per_case': 4,
        'development_calls': sum(p['split'] == 'development' for p in public) * 4,
        'all_candidate_calls': len(public) * 4,
        'source_mean_reported_cost_per_attempt': average,
        'source_p95_reported_cost_per_attempt': p95,
        'all_candidates_at_source_mean_usd': len(public) * 4 * average if average else None,
        'all_candidates_at_source_p95_usd': len(public) * 4 * p95 if p95 else None,
        'note': 'Historical arithmetic only; changed prompts/output lengths and retries can cost more. Not a quote, cap, or authorization.'}
    write_jsonl(out / 'public_cases.jsonl', public)
    write_jsonl(out / 'answer_keys.jsonl', keys)
    write_jsonl(out / 'argument_provenance.jsonl', provenance)
    write_jsonl(out / 'manual_review.jsonl', review)
    write_json(out / 'source_journal_hashes.json', journal_hashes)
    write_json(out / 'audit_summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=Path('runs/study-01'))
    parser.add_argument('--out', type=Path, default=Path('runs/recovery-01'))
    args = parser.parse_args()
    print(json.dumps(build(args.run, args.out), indent=2))
