import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dissent.cli import execute, score
from dissent.common import load_tasks, read_jsonl, validate_response, write_jsonl
from dissent.metrics import analyze, category, costs, rate
from dissent.protocols import PROTOCOLS, qualifies, review_context, run_task, strict_majority
from dissent.providers import CallStore, Config
from dissent.tasks import generate, save_dataset


def response(answer, **extra):
    return {"answer": answer, "reasoning": "Check the stated constraint.", "confidence": 0.9, **extra}


class ScriptedStore:
    """A deliberately known transition; correctness is never given to run_task."""
    def __init__(self, review_answer="A"):
        self.records = {}
        self.review_answer = review_answer
        self.seen = []

    def call(self, call_id, kind, task, context, messages):
        index = int(call_id.rsplit("/", 1)[1])
        if kind == "independent":
            value = response("A" if index == 0 else "B")
        elif kind == "debate":
            value = response("B")
        elif kind == "dissent":
            value = response("A" if index == 0 else "B", stance="DISSENT" if index == 0 else "AGREE",
                             disputed_claim="The proposed total violates a constraint." if index == 0 else "",
                             evidence="The constraint forces the alternative." if index == 0 else "")
        elif kind == "reconsider":
            value = response("A")
        else:
            value = response(self.review_answer)
        self.records[call_id] = {"call_id": call_id, "status": "ok", "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": 0.01}, "latency_seconds": 0.2}
        self.seen.append((kind, context, messages))
        return value


class DatasetTests(unittest.TestCase):
    def test_deterministic_verified_balanced_dataset(self):
        tasks, gold = generate(50, 2027)
        self.assertEqual((tasks, gold), generate(50, 2027))
        self.assertNotEqual(tasks, generate(50, 2028)[0])
        self.assertEqual(len({t["question"] for t in tasks}), 50)
        self.assertEqual({t["family"] for t in tasks}, {"ordering", "boolean", "shortest_path"})
        for task, key in zip(tasks, gold):
            self.assertEqual(task["options"][key["correct_answer"]], str(key["verified_value"]))
            self.assertEqual(len(key["verification"]["solvers"]), 2)
            self.assertNotIn("correct_answer", task)

    def test_gold_in_task_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.jsonl"
            tasks, _ = generate(1)
            tasks[0]["correct_answer"] = "A"
            write_jsonl(path, tasks)
            with self.assertRaises(ValueError):
                load_tasks(path)

    def test_multiple_seeds_all_exact_checks(self):
        for seed in range(8):
            self.assertEqual(len(generate(12, seed)[0]), 12)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.task = {"task_id": "test", "family": "fixture", "question": "Which option?", "options": {"A": "one", "B": "two", "C": "three", "D": "four"}}

    def test_strict_majority_and_fragmentation(self):
        self.assertIsNone(strict_majority(list(map(response, "AABBC"))))
        self.assertEqual(strict_majority(list(map(response, "AAABC"))), "A")
        self.assertEqual(category(list(map(response, "ABBBB")), "A"), "majority_wrong_minority_correct")
        self.assertEqual(category(list(map(response, "AABBC")), "C"), "no_strict_majority")
        self.assertEqual(category(list(map(response, "BBBBB")), "A"), "unanimous_wrong")

    def test_suppressed_original_can_dissent_and_recover(self):
        store = ScriptedStore()
        result = run_task(self.task, Config(), store)
        self.assertEqual(result["protocols"]["standard_debate"]["final_answer"], "B")
        self.assertEqual(result["protocols"]["protected_dissent"]["final_answer"], "A")
        self.assertEqual(result["protocols"]["protected_dissent_review"]["final_answer"], "A")
        self.assertEqual(len(store.records), 21)
        self.assertEqual([len(result["protocols"][p]["call_ids"]) for p in PROTOCOLS], [5, 10, 20, 16])
        first_dissent_context = next(c for k, c, _ in store.seen if k == "dissent")
        self.assertEqual(first_dissent_context["original"]["answer"], "A")
        self.assertEqual(first_dissent_context["current"]["answer"], "B")

    def test_appeal_unresolved_is_not_a_vote(self):
        result = run_task(self.task, Config(), ScriptedStore("UNRESOLVED"))
        self.assertIsNone(result["protocols"]["protected_dissent_review"]["final_answer"])
        self.assertEqual(result["protocols"]["protected_dissent_review"]["final_panel"][0]["answer"], "B")

    def test_threshold_and_structural_qualification(self):
        dissent = response("A", stance="DISSENT", disputed_claim="claim", evidence="evidence")
        self.assertTrue(qualifies(dissent, "B", 0.6))
        self.assertFalse(qualifies(dissent, "A", 0.6))
        self.assertFalse(qualifies({**dissent, "evidence": " "}, "B", 0.6))
        self.assertFalse(qualifies({**dissent, "confidence": 0.5}, "B", 0.6))
        result = run_task(self.task, Config(dissent_threshold=1.0), ScriptedStore())
        self.assertFalse(result["protocols"]["protected_dissent"]["escalated"])
        self.assertEqual(result["protocols"]["protected_dissent"]["final_answer"], "B")

    def test_review_has_two_unlabelled_arguments_no_counts_or_history(self):
        store = ScriptedStore()
        run_task(self.task, Config(), store)
        context = next(c for k, c, _ in store.seen if k == "review")
        self.assertEqual(set(context), {"candidates"})
        self.assertEqual(len(context["candidates"]), 2)
        for candidate in context["candidates"]:
            self.assertEqual(set(candidate), {"answer", "reasoning"})
        selected = response("A", disputed_claim="Four agents agree.", evidence="The constraint proves A.")
        context = review_context(self.task, [response("B")], [response("B")], "B", selected, 0)
        self.assertNotIn("Four agents", json.dumps(context))

    def test_invalid_model_output_rejected(self):
        for value in (response("Z"), response("A", confidence=True), response("A", confidence=float("nan")), response("A", reasoning=""), {**response("A"), "extra": 1}):
            with self.assertRaises(ValueError):
                validate_response(value, "independent", self.task)

    def test_no_majority_skips_closure_checkpoint(self):
        class Fragmented(ScriptedStore):
            def call(self, call_id, kind, task, context, messages):
                value = super().call(call_id, kind, task, context, messages)
                if kind == "debate":
                    value = response("AABBC"[int(call_id.rsplit("/", 1)[1])])
                return value
        store = Fragmented()
        result = run_task(self.task, Config(), store)
        self.assertEqual(result["declarations"], [])
        self.assertEqual(len(store.records), 10)
        self.assertIsNone(result["protocols"]["protected_dissent"]["final_answer"])

    def test_metrics_separate_panel_suppression_from_appeal(self):
        store = ScriptedStore()
        result = run_task(self.task, Config(), store)
        report = analyze([self.task], [{"task_id": "test", "correct_answer": "A"}], [result], store.records, "mock")
        baseline = report["protocols"]["standard_debate"]
        self.assertEqual(baseline["correct_minority_suppression"]["value"], 1)
        self.assertEqual(baseline["agent_transitions"]["correct_to_wrong"], 1)
        appeal = report["protocols"]["protected_dissent_review"]
        self.assertEqual(appeal["correct_minority_recovery"]["value"], 1)
        self.assertEqual(appeal["correct_minority_agent_survival"]["value"], 0)
        self.assertEqual(appeal["correct_minority_suppression"]["value"], 0)
        self.assertEqual(report["physical_cost"]["calls"], 21)
        self.assertEqual(appeal["standalone_cost"]["calls"], 16)
        majority = report["protocols"]["majority_vote"]
        self.assertEqual(majority["focus_wrong_final_answer"]["value"], 1)
        self.assertEqual(majority["correct_minority_suppression"]["value"], 0)

    def test_zero_denominators_and_unknown_cost(self):
        self.assertIsNone(rate(0, 0)["value"])
        self.assertEqual(rate(1, 1)["denominator"], 1)
        self.assertIsNone(costs([{"usage": {}}])["cost"])
        self.assertEqual(costs([{"usage": {}}])["cost_missing_calls"], 1)


class ExecutionTests(unittest.TestCase):
    def test_end_to_end_resume_and_score(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            save_dataset(root / "data", 6)
            tasks = load_tasks(root / "data/tasks.jsonl")
            first, records = execute(tasks, root / "run", Config())
            before = {p.name: p.read_bytes() for p in (root / "run/calls").glob("*.json")}
            second, _ = execute(tasks, root / "run", Config())
            self.assertEqual(first, second)
            self.assertEqual(before, {p.name: p.read_bytes() for p in (root / "run/calls").glob("*.json")})
            report = score(root / "data/tasks.jsonl", root / "data/answers.jsonl", root / "run")
            self.assertEqual(report["tasks"], 6)
            self.assertTrue(report["synthetic"])
            self.assertIn("SYNTHETIC", (root / "run/report.md").read_text())
            with self.assertRaises(ValueError):
                execute(tasks, root / "run", Config(seed=99))

    def test_budget_interruption_resumes_from_completed_calls(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            tasks, _ = generate(1)
            with self.assertRaises(RuntimeError):
                execute(tasks, directory, Config(), max_calls=2)
            self.assertEqual(len(list((Path(directory) / "calls").glob("*.json"))), 2)
            result, records = execute(tasks, directory, Config(), max_calls=21)
            self.assertEqual(len(result), 1)
            self.assertGreaterEqual(len(records), 10)

    def test_live_request_is_pinned_and_usage_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            task = generate(1)[0][0]
            raw = {"model": "model/version", "provider": "Pinned", "choices": [{"message": {"content": json.dumps(response("A"))}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9, "cost": 0.001}}
            fake_http = contextlib.nullcontext(io.BytesIO(json.dumps(raw).encode()))
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "secret-test-key"}), patch("urllib.request.urlopen", return_value=fake_http) as mocked:
                store = CallStore(directory, Config(backend="openrouter", model="model/version", provider="Pinned", send_seed=True))
                store.call("one", "independent", task, {}, [{"role": "user", "content": "problem"}])
                request = mocked.call_args.args[0]
                payload = json.loads(request.data)
                self.assertEqual(payload["provider"], {"only": ["Pinned"], "allow_fallbacks": False, "require_parameters": True})
                self.assertEqual(payload["plugins"], [])
                self.assertNotIn("tools", payload)
                self.assertIn("seed", payload)
                audit = next(Path(directory).glob("*.json")).read_text()
                self.assertNotIn("secret-test-key", audit)
                self.assertEqual(store.records["one"]["usage"]["total_tokens"], 9)

    def test_invalid_output_logged_and_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            task = generate(1)[0][0]
            store = CallStore(directory, Config())
            with patch("dissent.providers.mock_reply", return_value=response("invalid")) as mocked:
                with self.assertRaises(RuntimeError):
                    store.call("bad", "independent", task, {}, [])
                with self.assertRaises(RuntimeError):
                    store.call("bad", "independent", task, {}, [])
                self.assertEqual(mocked.call_count, 1)
                self.assertEqual(store.records["bad"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
