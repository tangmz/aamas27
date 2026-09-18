import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from dissent.common import read_jsonl, write_json, write_jsonl
from dissent.providers import BudgetExceeded
from dissent.reporting import write_study_report
from dissent.statistics import exact_mcnemar, holm_adjust, paired_inference
from dissent.study import execute_study, resolve_plan
from dissent.tasks import generate


def fixture(root):
    tasks, answers=generate(6,42)
    write_jsonl(root/'tasks.jsonl',tasks)
    write_jsonl(root/'answers.jsonl',answers)
    config={'name':'test','datasets':[{'id':'fresh','tasks':'tasks.jsonl','answers':'answers.jsonl'}],
            'models':[{'id':'fixture','backend':'mock','model':'mock-fixture-v1','provider':'offline'}],
            'seeds':[31,32],'suite':'research','selection':'disagreement',
            'limits':{'max_requests':600,'max_reported_cost_usd':1}, 'inference':{},
            'statistics':{'bootstrap_samples':200,'seed':7,'comparisons':[['protected_dissent','standard_debate'],['protected_dissent','extra_round_control']]}}
    write_json(root/'study.json',config)
    return root/'study.json',config


class StudyTests(unittest.TestCase):
    def test_staged_collection_reuse_report_and_call_matched_controls(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root=Path(folder)
            path, config=fixture(root)
            out=root/'run'
            execute_study(path,out,'independent')
            before={str(p):p.read_bytes() for p in out.glob('units/*/calls/*.json')}
            self.assertEqual(len(before),60)
            screening=write_study_report(out,screen_only=True)
            self.assertEqual(sum(r['panels'] for r in screening),12)
            execute_study(path,out,'deliberate')
            self.assertTrue(all(Path(p).read_bytes()==content for p,content in before.items()))
            report=write_study_report(out)
            self.assertTrue(report['synthetic'])
            self.assertEqual(len(report['descriptive']),9*5) # all, dataset, three families
            for p in out.glob('units/*/tasks/*.json'):
                result=json.loads(p.read_text())
                conditions=result['protocols']
                self.assertEqual(len(conditions['protected_dissent']['call_ids']),len(conditions['extra_round_control']['call_ids']))
                self.assertEqual(len(conditions['protected_dissent_review']['call_ids']),len(conditions['independent_review_control']['call_ids']))
            self.assertTrue(all(r['n_questions'] <= 6 for r in report['contrasts']))
            execute_study(path,out,'deliberate')
            self.assertEqual(report['resources'],write_study_report(out)['resources'])

    def test_budget_resume_and_identity_change(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root=Path(folder)
            path,config=fixture(root)
            config['limits']['max_requests']=3
            write_json(path,config)
            with self.assertRaises(BudgetExceeded): execute_study(path,root/'run','independent')
            config['limits']['max_requests']=600
            write_json(path,config)
            execute_study(path,root/'run','independent')
            config['selection']='all'
            write_json(path,config)
            with self.assertRaisesRegex(ValueError,'changed'): execute_study(path,root/'run','deliberate')

    def test_gold_mutation_rejected_in_reporting(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root=Path(folder)
            path,_=fixture(root)
            execute_study(path,root/'run','independent')
            with (root/'answers.jsonl').open('a') as stream: stream.write('\n')
            with self.assertRaisesRegex(ValueError,'Answer key changed'): write_study_report(root/'run',screen_only=True)

    def test_selection_never_uses_gold(self):
        from dissent.study import selected
        self.assertFalse(selected([{'answer':'A'}]*5,'disagreement'))
        self.assertTrue(selected([{'answer':'A'}]*4+[{'answer':'B'}],'disagreement'))
        self.assertTrue(selected([{'answer':'A'}]*5,'all'))


class StatisticalTests(unittest.TestCase):
    def test_mcnemar_known_cases(self):
        self.assertEqual(exact_mcnemar(0,0),1)
        self.assertAlmostEqual(exact_mcnemar(4,0),0.125)
        self.assertAlmostEqual(exact_mcnemar(10,10),1)

    def test_holm_monotonic_and_missing(self):
        self.assertEqual(holm_adjust([0.01,0.04,0.03,None]),[0.03,0.06,0.06,None])

    def test_bootstrap_keeps_repetitions_clustered(self):
        pairs=[{'task_id':str(i),'stratum':'one','treatment':i%2,'baseline':0} for i in range(4) for seed in range(3)]
        a=paired_inference(pairs,500,11)
        self.assertEqual(a,paired_inference(pairs,500,11))
        self.assertEqual(a['n_pairs'],12)
        self.assertEqual(a['n_questions'],4)
        self.assertEqual(a['difference'],0.5)
        self.assertEqual(a['test'],'exact_question_cluster_sign_flip')
        self.assertAlmostEqual(a['p_value'],0.5)

    def test_empty_focus_is_undefined(self):
        result=paired_inference([],200,1)
        self.assertIsNone(result['difference'])
        self.assertIsNone(result['p_value'])
        self.assertEqual(result['n_questions'],0)
