"""Dataset provenance, lossless conversion, and automatic classification checks."""

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from dissent.bbh import FAMILIES, build, convert_example
from dissent.common import load_tasks, read_jsonl
from dissent.metrics import classify_initial_panels

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/bbh_300"


class BBHTests(unittest.TestCase):
    def test_balanced_sample_and_original_answer_mapping(self):
        tasks = load_tasks(DATA / "tasks.jsonl")
        gold = {r["task_id"]: r for r in read_jsonl(DATA / "answers.jsonl")}
        provenance = {r["task_id"]: r for r in read_jsonl(DATA / "provenance.jsonl")}
        self.assertEqual(len(tasks), 300)
        self.assertEqual(Counter(t["family"] for t in tasks), {"bbh_" + f: 100 for f in FAMILIES})
        self.assertEqual(set(gold), set(provenance))
        raw = {f: json.loads((DATA / "raw/bbh" / (f + ".json")).read_text(encoding="utf-8"))["examples"] for f in FAMILIES}
        for task in tasks:
            origin = provenance[task["task_id"]]
            family = task["family"].removeprefix("bbh_")
            example = raw[family][origin["source_index_zero_based"]]
            converted, answer, _ = convert_example(family, origin["source_index_zero_based"], example)
            self.assertEqual(task, converted)
            self.assertEqual(gold[task["task_id"]], answer)
            self.assertNotIn("correct_answer", task)

    def test_offline_rebuild_matches_checked_in_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            tasks, answers = build(DATA / "raw", directory)
            self.assertEqual(tasks, read_jsonl(DATA / "tasks.jsonl"))
            self.assertEqual(answers, read_jsonl(DATA / "answers.jsonl"))
            with self.assertRaises(ValueError):
                build(DATA / "raw", directory)

    def test_reject_malformed_target_or_options(self):
        path = DATA / "raw/bbh/logical_deduction_five_objects.json"
        example = json.loads(path.read_text(encoding="utf-8"))["examples"][0]
        for broken in ({**example, "target": "(Z)"}, {**example, "input": example["input"].replace("(B)", "(A)")}, {**example, "input": "no options"}):
            with self.assertRaises(ValueError):
                convert_example(FAMILIES[0], 0, broken)

    def test_automatic_classification_all_categories(self):
        panels = {"minority_correct": "ABBBB", "majority_correct": "AAABB", "all_correct": "AAAAA",
                  "all_wrong": "BBBBB", "fragmented": "AABBC", "no_correct": "BBBCC"}
        expected = ["majority_wrong_minority_correct", "majority_correct_minority_wrong", "unanimous_correct",
                    "unanimous_wrong", "no_strict_majority", "majority_wrong_no_correct_agent"]
        results = [{"task_id": key, "initial": [{"answer": a} for a in answers]} for key, answers in panels.items()]
        rows = classify_initial_panels(results, {key: "A" for key in panels})
        self.assertEqual([r["initial_category"] for r in rows], expected)
        self.assertEqual(rows[0]["correct_agent_indices_zero_based"], [0])
        self.assertEqual(rows[0]["answer_counts"], {"A": 1, "B": 4})
        self.assertIsNone(rows[4]["initial_majority_answer"])


if __name__ == "__main__":
    unittest.main()
