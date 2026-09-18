"""Command-line entry points for generation, execution, and post-hoc scoring."""

import argparse
import json
import platform
import random
import sys
from dataclasses import asdict
from pathlib import Path

from .common import digest, load_tasks, read_jsonl, utc_now, write_json, write_jsonl
from .environment import check_environment, load_env, model_settings
from .metrics import analyze, classify_initial_panels, render_report
from .protocols import PROTOCOLS, run_task
from .providers import CallStore, Config
from .tasks import save_dataset


def source_hash():
    return digest({p.name: p.read_text(encoding="utf-8-sig") for p in sorted(Path(__file__).parent.glob("*.py"))})


def execute(tasks, directory, config, max_calls=1100, retry_failed=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    identity = {"config": asdict(config), "tasks_sha256": digest(tasks), "source_sha256": source_hash(), "protocols": list(PROTOCOLS)}
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["identity"] != identity:
            raise ValueError("Run configuration, source code, or tasks changed; use a new run directory")
    else:
        if any(directory.iterdir()):
            raise ValueError("Run directory contains files but has no manifest")
        manifest = {"identity": identity, "started_at": utc_now(), "python": sys.version, "platform": platform.platform(), "synthetic": config.backend == "mock"}
    manifest.update(status="running", last_started_at=utc_now(), max_calls=max_calls)
    write_json(manifest_path, manifest)
    store = CallStore(directory / "calls", config, max_calls, retry_failed)
    order = list(tasks)
    random.Random(config.seed).shuffle(order)
    manifest["task_order"] = [t["task_id"] for t in order]
    write_json(manifest_path, manifest)
    results = []
    try:
        for index, task in enumerate(order, 1):
            result = run_task(task, config, store)
            results.append(result)
            write_json(directory / "results" / (digest(task["task_id"]) + ".json"), result)
            print(f'[{index}/{len(tasks)}] {task["task_id"]}', flush=True)
    except BaseException:
        manifest.update(status="interrupted", finished_at=utc_now(), completed_tasks=len(results))
        write_json(manifest_path, manifest)
        raise
    manifest.update(status="complete", finished_at=utc_now(), completed_tasks=len(results), physical_calls=len(store.records))
    write_json(manifest_path, manifest)
    return results, store.records


def score(tasks_path, answers_path, directory):
    directory = Path(directory)
    tasks = load_tasks(tasks_path)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "complete":
        raise ValueError("Run is incomplete; resume it before scoring")
    if manifest["identity"]["tasks_sha256"] != digest(tasks):
        raise ValueError("Tasks do not match the run")
    results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((directory / "results").glob("*.json"))]
    record_list = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((directory / "calls").glob("*.json"))]
    records = {r["call_id"]: r for r in record_list}
    if len(records) != len(record_list) or any(r["status"] != "ok" for r in record_list):
        raise ValueError("Run contains duplicate, failed, or pending calls")
    gold = read_jsonl(answers_path)
    report = analyze(tasks, gold, results, records, manifest["identity"]["config"]["backend"])
    write_jsonl(directory / "classifications.jsonl", classify_initial_panels(results, {r["task_id"]: r["correct_answer"] for r in gold}))
    report["answer_key_sha256"] = digest(gold)
    report["run_identity"] = manifest["identity"]
    write_json(directory / "summary.json", report)
    (directory / "report.md").write_text(render_report(report), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Protected dissent pilot; offline by default")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-config", help="Validate local OpenRouter settings without network access or displaying values")
    generate = sub.add_parser("generate", help="Generate and exactly verify fresh tasks")
    generate.add_argument("--out", type=Path, default=Path("data/pilot"))
    generate.add_argument("--count", type=int, default=50)
    generate.add_argument("--seed", type=int, default=2027)
    run = sub.add_parser("run", help="Run four paired protocols; never reads the answer key")
    run.add_argument("--tasks", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--backend", choices=["mock", "openrouter"], default="mock")
    run.add_argument("--model", help="Overrides OPENROUTER_MODEL for live runs")
    run.add_argument("--provider", help="Overrides OPENROUTER_PROVIDER for live runs")
    run.add_argument("--seed", type=int, default=2027)
    run.add_argument("--temperature", type=float, default=0.7)
    run.add_argument("--top-p", type=float, default=1.0)
    run.add_argument("--max-tokens", type=int, default=800)
    run.add_argument("--send-seed", action="store_true", help="Require provider support for the derived per-call seed")
    run.add_argument("--dissent-threshold", type=float, default=0.6)
    run.add_argument("--max-calls", type=int, default=1100, help="Request-attempt cap including retries and resumed calls")
    run.add_argument("--max-attempts", type=int, default=4, help="Maximum attempts per transient-failure batch")
    run.add_argument("--retry-failed", action="store_true", help="Resume recorded transient or ambiguous failures with another bounded batch")
    analyze_parser = sub.add_parser("analyze", help="Score a completed run")
    analyze_parser.add_argument("--tasks", type=Path, required=True)
    analyze_parser.add_argument("--answers", type=Path, required=True)
    analyze_parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "check-config":
            load_env()
            print(check_environment())
        elif args.command == "generate":
            save_dataset(args.out, args.count, args.seed)
            print(f"Wrote {args.count} verified tasks to {args.out}")
        elif args.command == "run":
            if args.backend == "openrouter":
                load_env()
            model, provider = model_settings(args.backend, args.model, args.provider)
            config = Config(backend=args.backend, model=model, provider=provider, seed=args.seed, temperature=args.temperature,
                            top_p=args.top_p, max_tokens=args.max_tokens, send_seed=args.send_seed, dissent_threshold=args.dissent_threshold, max_attempts=args.max_attempts)
            config.validate()
            if args.max_calls < 1:
                raise ValueError("max-calls must be positive")
            tasks = load_tasks(args.tasks)
            print(f"Backend: {config.backend}. Upper bound: {21 * len(tasks)} physical calls; configured cap: {args.max_calls}.")
            execute(tasks, args.out, config, args.max_calls, args.retry_failed)
        else:
            score(args.tasks, args.answers, args.run)
            print(f"Report: {args.run / 'report.md'}")
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        parser.exit(1, f"Error: {exc}\n")
