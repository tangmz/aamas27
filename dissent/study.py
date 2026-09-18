"""Two-stage experiment orchestration. Run python -m dissent.study --help."""

import argparse
import json
import os
import platform
import random
import re
import secrets
from dataclasses import asdict
from pathlib import Path

from .common import digest, load_tasks, read_jsonl, utc_now, write_json, write_jsonl
from .environment import load_env
from .providers import BudgetExceeded, CallFailure, CallStore, Config
from .protocols import PROTOCOLS, run_task
from .research_protocols import RESEARCH_PROTOCOLS, independent_panel, run_research_task, stopped_result
from .tasks import save_dataset


def source_hash():
    return digest({p.name: p.read_text(encoding="utf-8-sig") for p in sorted(Path(__file__).parent.glob("*.py"))})


def prepare(out, public=Path("data/bbh_300"), seed=None):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Preparation destination must be empty")
    public_tasks = load_tasks(Path(public) / "tasks.jsonl")
    if len(public_tasks) != 300:
        raise ValueError("Expected 300 public questions")
    seed = secrets.randbelow(2**31) if seed is None else seed
    generated = save_dataset(out / "fresh", 300, seed)
    write_json(out / "manifest.json", {"prepared_at": utc_now(), "fresh_seed": seed, "fresh_count": len(generated),
               "public_count": len(public_tasks), "public_tasks_sha256": digest(public_tasks),
               "instruction": "Freeze for evaluation after a disjoint development preflight; do not tune on evaluation outcomes."})


def resolve_plan(path):
    path = Path(path).resolve()
    spec = json.loads(path.read_text(encoding="utf-8-sig"))
    required = {"name", "datasets", "models", "seeds", "suite", "selection", "limits", "inference", "statistics"}
    if set(spec) != required:
        raise ValueError(f"Study config requires exactly {sorted(required)}")
    if spec["suite"] not in {"pilot", "research"} or spec["selection"] not in {"all", "disagreement"}:
        raise ValueError("Unknown suite or selection policy")
    if not spec["seeds"] or len(set(spec["seeds"])) != len(spec["seeds"]) or any(type(x) is not int for x in spec["seeds"]):
        raise ValueError("Provide unique integer repetition seeds")
    if not spec["datasets"] or not spec["models"]:
        raise ValueError("At least one dataset and model required")
    limits = spec["limits"]
    if set(limits) != {"max_requests", "max_reported_cost_usd"} or type(limits["max_requests"]) is not int or limits["max_requests"] < 1:
        raise ValueError("Set a positive integer max_requests and max_reported_cost_usd (or null)")
    import math
    if limits["max_reported_cost_usd"] is not None and (not isinstance(limits["max_reported_cost_usd"], (float, int)) or not math.isfinite(limits["max_reported_cost_usd"]) or limits["max_reported_cost_usd"] <= 0):
        raise ValueError("Invalid reported-cost stop threshold")
    stats = spec["statistics"]
    if set(stats) != {"bootstrap_samples", "seed", "comparisons"} or type(stats["bootstrap_samples"]) is not int or stats["bootstrap_samples"] < 200:
        raise ValueError("Statistics requires bootstrap_samples >= 200, seed, and comparisons")
    protocols = RESEARCH_PROTOCOLS if spec["suite"] == "research" else PROTOCOLS
    if type(stats["seed"]) is not int:
        raise ValueError("Statistics seed must be an integer")
    if not stats["comparisons"] or any(len(pair) != 2 or pair[0] == pair[1] or any(p not in protocols for p in pair) for pair in stats["comparisons"]):
        raise ValueError("Invalid planned protocol comparisons")
    if len({tuple(pair) for pair in stats["comparisons"]}) != len(stats["comparisons"]):
        raise ValueError("Duplicate planned comparison")
    tasks, sources, seen = [], [], set()
    for dataset in spec["datasets"]:
        if set(dataset) != {"id", "tasks", "answers"} or not dataset["id"] or dataset["id"] in seen:
            raise ValueError("Dataset requires unique id, tasks and answers")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", dataset["id"]) or dataset["id"] == "all":
            raise ValueError("Dataset IDs must be simple identifiers; all is reserved")
        seen.add(dataset["id"])
        task_path = (path.parent / dataset["tasks"]).resolve()
        answer_path = (path.parent / dataset["answers"]).resolve()
        public = load_tasks(task_path)
        source = {**dataset, "tasks_path": str(task_path), "answers_path": str(answer_path), "tasks_sha256": digest(public),
                  "answers_file_sha256": __import__('hashlib').sha256(answer_path.read_bytes()).hexdigest(), "count": len(public)}
        sources.append(source)
        for task in public:
            tasks.append({**task, "task_id": dataset["id"] + "::" + task["task_id"]})
    models, seen = [], set()
    for model in spec["models"]:
        if set(model) != {"id", "backend", "model", "provider"} or model["id"] in seen or not model["id"]:
            raise ValueError("Model requires unique id, backend, model and provider")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", model["id"]):
            raise ValueError("Model IDs must be simple identifiers")
        seen.add(model["id"])
        entry = dict(model)
        for field, name in (("model", "OPENROUTER_MODEL"), ("provider", "OPENROUTER_PROVIDER")):
            if entry[field] == "$" + name:
                entry[field] = os.environ.get(name, "")
        for seed in spec["seeds"]:
            Config(backend=entry["backend"], model=entry["model"], provider=entry["provider"], seed=seed, **spec["inference"]).validate()
        models.append(entry)
    if len({t["task_id"] for t in tasks}) != len(tasks):
        raise ValueError("Composite task IDs collide")
    identity = {"name": spec["name"], "sources": sources, "models": models, "seeds": spec["seeds"], "suite": spec["suite"],
                "selection": spec["selection"], "inference": spec["inference"], "statistics": stats, "tasks_sha256": digest(tasks), "source_sha256": source_hash()}
    return spec, identity, tasks


def gold_for(identity):
    gold = {}
    for source in identity["sources"]:
        path = Path(source["answers_path"])
        if __import__('hashlib').sha256(path.read_bytes()).hexdigest() != source["answers_file_sha256"]:
            raise ValueError("Answer key changed since collection")
        for row in read_jsonl(path):
            key = source["id"] + "::" + row["task_id"]
            if key in gold:
                raise ValueError("Duplicate gold ID")
            gold[key] = row["correct_answer"]
    return gold


def selected(initial, selection):
    return selection == "all" or len({r["answer"] for r in initial}) > 1


def execute_study(config_path, out, stage, live=False, retry_failed=False):
    if stage not in {"independent", "deliberate"}:
        raise ValueError("Invalid study stage")
    load_env()
    spec, identity, tasks = resolve_plan(config_path)
    if not live and any(m["backend"] != "mock" for m in identity["models"]):
        raise ValueError("Live collection requires --live; planning/reporting do not make model calls")
    out = Path(out)
    manifest_path = out / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["identity"] != identity:
            raise ValueError("Study source, datasets, model settings or analysis plan changed; use a new directory")
    else:
        if stage == "deliberate":
            raise ValueError("Collect independent panels first")
        if out.exists() and any(out.iterdir()):
            raise ValueError("Study output must be empty or have a matching manifest")
        manifest = {"identity": identity, "created_at": utc_now(), "runtime": {"python": platform.python_version(), "platform": platform.platform()}, "invocations": []}
        write_jsonl(out / "tasks.jsonl", tasks)
    manifest["invocations"].append({"stage": stage, "started_at": utc_now(), "limits": spec["limits"], "retry_failed": retry_failed})
    manifest.update(status="running", stage=stage)
    write_json(manifest_path, manifest)
    stores, units = [], []
    for model in identity["models"]:
        for seed in identity["seeds"]:
            label = digest([model["id"], seed])[:16]
            unit_path = out / "units" / label
            config = Config(backend=model["backend"], model=model["model"], provider=model["provider"], seed=seed, **spec["inference"])
            store = CallStore(unit_path / "calls", config, spec["limits"]["max_requests"], retry_failed)
            units.append((model, seed, unit_path, store))
            stores.append(store)
            write_json(unit_path / "unit.json", {"model_id": model["id"], "seed": seed, "config": asdict(config)})

    def budget_guard():
        if sum(s.attempt_count for s in stores) >= spec["limits"]["max_requests"]:
            raise BudgetExceeded("Study request-attempt cap reached; increase limits.max_requests to resume")
        threshold = spec["limits"]["max_reported_cost_usd"]
        known = sum(s.known_cost for s in stores)
        if threshold is not None and known >= threshold:
            raise BudgetExceeded("Reported-cost stop threshold reached; unknown charges may be additional")

    for store in stores:
        store.before_attempt = budget_guard
    failures = 0
    try:
        if stage == "deliberate":
            for _, _, unit_path, _ in units:
                if not (unit_path / "independent_complete.json").exists():
                    raise ValueError("Finish the independent stage for every model/seed before deliberation")
        for model, seed, unit_path, store in units:
            order = list(tasks)
            random.Random(seed).shuffle(order)
            for number, task in enumerate(order, 1):
                task_path = unit_path / "tasks" / (digest(task["task_id"]) + ".json")
                existing = json.loads(task_path.read_text(encoding="utf-8")) if task_path.exists() else {}
                if stage == "independent" and existing.get("initial"):
                    continue
                if stage == "deliberate" and existing.get("status") == "complete":
                    continue
                try:
                    if stage == "independent":
                        initial = independent_panel(task, store.config, store)
                        record = {"task_id": task["task_id"], "initial": initial, "selected": selected(initial, identity["selection"]), "status": "independent_complete"}
                    else:
                        if not existing.get("initial"):
                            failures += 1
                            continue
                        if existing["selected"]:
                            run = run_research_task if identity["suite"] == "research" else run_task
                            record = run(task, store.config, store)
                        else:
                            record = stopped_result(task, existing["initial"], RESEARCH_PROTOCOLS if identity["suite"] == "research" else PROTOCOLS)
                        record.update(selected=existing["selected"], status="complete")
                    write_json(task_path, record)
                except CallFailure:
                    failures += 1
                    record = {**existing, "task_id": task["task_id"], "status": stage + "_failed"}
                    write_json(task_path, record)
                    fatal = any(r.get("status") == "error" and r.get("attempts", [{}])[-1].get("http_status") in {400, 401, 402, 403, 404, 422} and not r.get("retryable") for r in store.records.values())
                    if fatal:
                        raise CallFailure("Permanent API configuration/authentication error; stopping study") from None
                print(f'{stage}: {model["id"]}, seed {seed}, {number}/{len(tasks)}', flush=True)
            if stage == "independent":
                write_json(unit_path / "independent_complete.json", {"finished_at": utc_now(), "tasks_attempted": len(tasks)})
    except BaseException:
        manifest.update(status="interrupted", finished_at=utc_now())
        write_json(manifest_path, manifest)
        raise
    manifest.update(status="complete_with_failures" if failures else "complete", finished_at=utc_now(), failures_this_invocation=failures)
    write_json(manifest_path, manifest)
    return manifest



def preflight(config_path, out, live=False):
    """Three newly generated development questions; no evaluation questions used."""
    import copy
    load_env()
    spec, identity, _ = resolve_plan(config_path)
    out = Path(out).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("Use a new preflight directory")
    if not live and any(m["backend"] != "mock" for m in identity["models"]):
        raise ValueError("Live preflight requires --live")
    save_dataset(out / "development", 3, secrets.randbelow(2**31))
    trial = copy.deepcopy(spec)
    trial["name"] += "-preflight"
    trial["datasets"] = [{"id": "development", "tasks": "development/tasks.jsonl", "answers": "development/answers.jsonl"}]
    trial["seeds"] = spec["seeds"][:1]
    trial["selection"] = "all"
    trial["limits"]["max_requests"] = min(spec["limits"]["max_requests"], 3 * 47 * len(spec["models"]) * spec["inference"].get("max_attempts", 4))
    threshold = trial["limits"]["max_reported_cost_usd"]
    trial["limits"]["max_reported_cost_usd"] = min(threshold, 1.0) if threshold is not None else 1.0
    write_json(out / "config.json", trial)
    execute_study(out / "config.json", out / "run", "independent", live)
    execute_study(out / "config.json", out / "run", "deliberate", live)
    from .reporting import write_study_report
    return write_study_report(out / "run")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Prepare 300 fresh questions for the 600-question study")
    prep.add_argument("--out", type=Path, default=Path("data/study_600"))
    prep.add_argument("--public", type=Path, default=Path("data/bbh_300"))
    prep.add_argument("--seed", type=int)
    pre = sub.add_parser("preflight", help="Run three disjoint development questions through the configured suite")
    pre.add_argument("--config", type=Path, required=True)
    pre.add_argument("--out", type=Path, required=True)
    pre.add_argument("--live", action="store_true")
    plan = sub.add_parser("plan", help="Validate a config and display call bounds, without model calls")
    plan.add_argument("--config", type=Path, required=True)
    for name in ("independent", "deliberate"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--out", type=Path, required=True)
        command.add_argument("--live", action="store_true")
        command.add_argument("--retry-failed", action="store_true", help="Permit another bounded attempt batch for transient/ambiguous recorded failures")
    for name in ("screen", "report"):
        command = sub.add_parser(name)
        command.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.out, args.public, args.seed)
            print(f"Prepared fresh dataset in {args.out}")
        elif args.command == "preflight":
            preflight(args.config, args.out, args.live)
            print(f"Preflight results: {args.out / 'run'}")
        elif args.command == "plan":
            load_env()
            spec, identity, tasks = resolve_plan(args.config)
            panels = len(tasks) * len(identity["models"]) * len(identity["seeds"])
            upper = 47 if identity["suite"] == "research" else 21
            print(json.dumps({"questions": len(tasks), "model_seed_panels": panels, "independent_calls": 5 * panels,
                              "full_suite_logical_call_upper_bound": upper * panels, "selection": identity["selection"], "limits": spec["limits"],
                              "note": "Retries consume request cap. Reported-cost threshold is not a hard monetary cap."}, indent=2))
        elif args.command in {"screen", "report"}:
            from .reporting import write_study_report
            write_study_report(args.run, screen_only=args.command == "screen")
            print(f"Wrote {'screening' if args.command == 'screen' else 'analysis'} outputs to {args.run}")
        else:
            execute_study(args.config, args.out, args.command, args.live, args.retry_failed)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
