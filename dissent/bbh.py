"""Pinned BBH acquisition and deterministic multiple-choice conversion.

Run: python -m dissent.bbh --out data/bbh_300
No model calls are made. Original downloaded files remain unchanged.
"""

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

from .common import digest, load_tasks, utc_now, write_json, write_jsonl

REVISION = "9ee07bd481feebf959a6b59d61ea57bdcf30964d"
REPOSITORY = "https://github.com/suzgunmirac/BIG-Bench-Hard"
FAMILIES = ("logical_deduction_five_objects", "logical_deduction_seven_objects", "tracking_shuffled_objects_seven_objects")
FILES = ("LICENSE", "README.md", "bbh/README.md") + tuple(f"bbh/{family}.json" for family in FAMILIES)


def sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def convert_example(family, index, example):
    text = example["input"]
    question, marker, option_text = text.rpartition("\nOptions:\n")
    if not marker or not question.strip():
        raise ValueError(f"Missing option boundary: {family}:{index}")
    options = {}
    for line in option_text.splitlines():
        match = re.fullmatch(r"\(([A-Z])\) (.+)", line)
        if not match or match[1] in options:
            raise ValueError(f"Invalid or duplicate option: {family}:{index}")
        options[match[1]] = match[2]
    expected = 5 if family == "logical_deduction_five_objects" else 7
    if list(options) != list("ABCDEFG"[:expected]):
        raise ValueError(f"Unexpected option labels: {family}:{index}")
    target = re.fullmatch(r"\(([A-Z])\)", example["target"])
    if not target or target[1] not in options:
        raise ValueError(f"Invalid target: {family}:{index}")
    task_id = f"bbh/{family}/{index:04d}"
    task = {"task_id": task_id, "family": f"bbh_{family}", "question": question, "options": options}
    gold = {"task_id": task_id, "correct_answer": target[1]}
    provenance = {"task_id": task_id, "source_file": f"bbh/{family}.json", "source_index_zero_based": index,
                  "source_example_sha256": digest(example)}
    # Verify that splitting and re-rendering has preserved the original input exactly.
    reconstructed = question + "\nOptions:\n" + "\n".join(f"({k}) {v}" for k, v in options.items())
    if reconstructed != text:
        raise ValueError(f"Conversion changed source text: {family}:{index}")
    return task, gold, provenance


def build(raw_directory, directory, per_family=100, seed=2027):
    raw_directory, directory = Path(raw_directory), Path(directory)
    if not 1 <= per_family <= 250:
        raise ValueError("per-family must be between 1 and 250")
    if any((directory / name).exists() for name in ("tasks.jsonl", "answers.jsonl", "manifest.json", "provenance.jsonl")):
        raise ValueError("Prepared dataset already exists; choose a fresh output directory")
    tasks, answers, provenance, source_counts, sample_indices = [], [], [], {}, {}
    source_record = json.loads((raw_directory / "sources.json").read_text(encoding="utf-8"))
    if source_record["revision"] != REVISION or set(source_record["files"]) != set(FILES):
        raise ValueError("Source record does not match the pinned BBH release")
    for name, record in source_record["files"].items():
        if sha256_bytes((raw_directory / name).read_bytes()) != record["sha256"]:
            raise ValueError(f"Source checksum mismatch: {name}")
    seen = set()
    for family in FAMILIES:
        raw = json.loads((raw_directory / "bbh" / f"{family}.json").read_text(encoding="utf-8"))
        examples = raw["examples"]
        if len(examples) < per_family:
            raise ValueError(f"Not enough examples: {family}")
        # Validate all source rows, not just the selected sample.
        converted = [convert_example(family, i, row) for i, row in enumerate(examples)]
        source_counts[family] = len(examples)
        ranked = sorted(range(len(examples)), key=lambda i: (digest([seed, family, i]), i))
        indices = sorted(ranked[:per_family])
        sample_indices[family] = indices
        for i in indices:
            task, gold, origin = converted[i]
            if digest([task["question"], task["options"]]) in seen:
                raise ValueError("Duplicate question in the selected dataset")
            seen.add(digest([task["question"], task["options"]]))
            tasks.append(task)
            answers.append(gold)
            provenance.append(origin)
    write_jsonl(directory / "tasks.jsonl", tasks)
    write_jsonl(directory / "answers.jsonl", answers)
    write_jsonl(directory / "provenance.jsonl", provenance)
    load_tasks(directory / "tasks.jsonl")
    write_json(directory / "manifest.json", {"dataset": "BBH public reasoning subset", "preparer_version": "bbh-v1",
               "repository": REPOSITORY, "revision": REVISION, "prepared_at": utc_now(), "count": len(tasks),
               "per_family": per_family, "seed": seed, "sampling": "lowest SHA256 of canonical JSON [seed, family, zero-based index]; output in source order",
               "source_counts": source_counts, "selected_source_indices": sample_indices,
               "tasks_sha256": digest(tasks), "answers_sha256": digest(answers), "provenance_sha256": digest(provenance),
               "source_record": source_record, "ground_truth": "Original benchmark target labels; format/mapping validated, not independently re-solved",
               "contamination": "Public benchmark; prior model exposure cannot be excluded"})
    return tasks, answers


def download(raw_directory):
    raw_directory = Path(raw_directory)
    if raw_directory.exists() and any(raw_directory.iterdir()):
        raise ValueError("Raw destination must be empty; use --raw to prepare an existing verified download")
    downloaded = {}
    for name in FILES:
        url = f"https://raw.githubusercontent.com/suzgunmirac/BIG-Bench-Hard/{REVISION}/{name}"
        request = urllib.request.Request(url, headers={"User-Agent": "right-to-dissent-research"})
        with urllib.request.urlopen(request, timeout=30) as response:
            downloaded[name] = (url, response.read())
    # No files are saved until every download succeeds.
    records = {}
    for name, (url, content) in downloaded.items():
        path = raw_directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        records[name] = {"url": url, "sha256": sha256_bytes(content), "bytes": len(content)}
    write_json(raw_directory / "sources.json", {"repository": REPOSITORY, "revision": REVISION, "retrieved_at": utc_now(), "files": records})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/bbh_300"))
    parser.add_argument("--raw", type=Path, help="Reuse the raw directory of a prior download, without network access")
    parser.add_argument("--per-family", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2027)
    args = parser.parse_args()
    try:
        if not 1 <= args.per_family <= 250:
            raise ValueError("per-family must be between 1 and 250")
        raw = args.raw or args.out / "raw"
        if args.raw is None:
            download(raw)
        tasks, _ = build(raw, args.out, args.per_family, args.seed)
        print(f"Prepared {len(tasks)} BBH questions in {args.out}; revision {REVISION}")
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
