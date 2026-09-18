"""Study data integrity, denominators, cost accounting and statistical exports."""

import json
from collections import Counter, defaultdict
from pathlib import Path

from .common import digest, load_tasks, seed_for, write_json, write_jsonl
from .metrics import category, costs
from .protocols import PROTOCOLS
from .providers import compact_record
from .research_protocols import RESEARCH_PROTOCOLS
from .statistics import holm_adjust, paired_inference
from .study import gold_for, selected, source_hash

FOCUS = "majority_wrong_minority_correct"


def load_study(run):
    run = Path(run)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    identity = manifest["identity"]
    tasks = load_tasks(run / "tasks.jsonl")
    if digest(tasks) != identity["tasks_sha256"]:
        raise ValueError("Study task snapshot was modified")
    gold = gold_for(identity)
    if set(gold) != {t["task_id"] for t in tasks} or any(gold[t["task_id"]] not in t["options"] for t in tasks):
        raise ValueError("Gold must cover exactly all tasks with valid answer labels")
    units = []
    for model in identity["models"]:
        for seed in identity["seeds"]:
            path = run / "units" / digest([model["id"], seed])[:16]
            if not (path / "unit.json").exists():
                raise ValueError("Missing planned model/seed unit")
            unit = json.loads((path / "unit.json").read_text(encoding="utf-8"))
            if unit["model_id"] != model["id"] or unit["seed"] != seed:
                raise ValueError("Unit metadata mismatch")
            results = {}
            for file in sorted((path / "tasks").glob("*.json")):
                result = json.loads(file.read_text(encoding="utf-8"))
                if result["task_id"] in results or result["task_id"] not in gold:
                    raise ValueError("Duplicate or unexpected task result")
                results[result["task_id"]] = result
            records = {}
            for file in sorted((path / "calls").glob("*.json")):
                record = json.loads(file.read_text(encoding="utf-8"))
                if record["call_id"] in records:
                    raise ValueError("Duplicate call ID")
                records[record["call_id"]] = compact_record(record)
            units.append((model, seed, results, records))
    return manifest, tasks, gold, units


def materialize(run):
    manifest, tasks, gold, units = load_study(run)
    protocols = RESEARCH_PROTOCOLS if manifest["identity"]["suite"] == "research" else PROTOCOLS
    rows, screening, audits = [], [], []
    for model, seed, results, records in units:
        audit = costs(list(records.values()))
        audit.update(model_id=model["id"], seed=seed, failed_calls=sum(r["status"] == "error" for r in records.values()),
                     pending_calls=sum(r["status"] in {"pending", "paused"} for r in records.values()))
        audits.append(audit)
        for task in tasks:
            task_id = task["task_id"]
            result = results.get(task_id, {})
            initial = result.get("initial")
            if initial and (len(initial) != 5 or any(r["answer"] not in task["options"] for r in initial)):
                raise ValueError("Invalid independent panel")
            if initial:
                expected = [records[f"{task_id}/independent/{i}"]["parsed"] for i in range(5)]
                if initial != expected or result.get("selected") != selected(initial, manifest["identity"]["selection"]):
                    raise ValueError("Initial panel or selection differs from audited calls/policy")
            correct = gold[task_id]
            source = task_id.split("::", 1)[0]
            label = category(initial, correct) if initial else "initial_unavailable"
            meta = {"model_id": model["id"], "backend": model["backend"], "seed": seed, "task_id": task_id,
                    "dataset": source, "family": task["family"], "initial_category": label, "selected": result.get("selected"),
                    "initial_available": bool(initial), "collection_status": result.get("status", "not_collected")}
            screening.append({**meta, "correct_answer": correct, "initial_answers": [r["answer"] for r in initial] if initial else [],
                              "vote_counts": dict(Counter(r["answer"] for r in initial)) if initial else {},
                              "correct_agent_indices_zero_based": [i for i, r in enumerate(initial or []) if r["answer"] == correct]})
            for protocol in protocols:
                outcome = result.get("protocols", {}).get(protocol)
                if outcome is None and protocol == "majority_vote" and initial:
                    from .research_protocols import stopped_result
                    outcome = stopped_result(task, initial, [protocol])["protocols"][protocol]
                available = outcome is not None
                row = {**meta, "protocol": protocol, "available": available, "final_answer": None,
                       "correct": None, "resolved": None, "suppression": None, "surviving_correct_agents": None,
                       "initial_correct_agents": sum(r["answer"] == correct for r in initial or []),
                       "correct_to_correct": None, "correct_to_wrong": None, "wrong_to_correct": None, "wrong_to_wrong": None,
                       "false_dissent_count": 0, "dissent_count": 0, "qualifying_dissent_count": 0, "false_qualifying_dissent_count": 0, "escalated": None, "calls": None,
                       "request_attempts": None, "tokens": None, "cost_usd": None, "latency_seconds": None}
                if available:
                    if len(set(outcome["call_ids"])) != len(outcome["call_ids"]):
                        raise ValueError("Repeated logical call in an outcome")
                    called = [records[cid] for cid in outcome["call_ids"]]
                    if any(r["status"] != "ok" for r in called):
                        raise ValueError("Completed outcome references unsuccessful call")
                    panel = outcome["final_panel"]
                    if len(panel) != 5 or any(r["answer"] not in task["options"] for r in panel):
                        raise ValueError("Invalid final panel")
                    final = outcome["final_answer"]
                    if final is not None and final not in task["options"]:
                        raise ValueError("Invalid final answer")
                    resource = costs(called)
                    row.update(final_answer=final, correct=final == correct, resolved=final is not None,
                               suppression=final is not None and final != correct and {r["answer"] for r in panel} == {final},
                               surviving_correct_agents=sum(before["answer"] == correct and after["answer"] == correct for before, after in zip(initial, panel)),
                               escalated=outcome["escalated"], calls=resource["calls"], request_attempts=resource["request_attempts"],
                               tokens=resource["total_tokens"], cost_usd=resource["cost"], latency_seconds=resource["latency_seconds_sum"])
                    for first in ("correct", "wrong"):
                        for second in ("correct", "wrong"):
                            row[first + "_to_" + second] = sum((before["answer"] == correct) == (first == "correct") and (after["answer"] == correct) == (second == "correct") for before, after in zip(initial, panel))
                    declarations = result.get("declarations", []) if protocol in {"protected_dissent", "protected_dissent_review"} else result.get("controls", {}).get("explicit_dissent", []) if protocol == "explicit_dissent" else []
                    declarations = [d for d in declarations if d["stance"] == "DISSENT"]
                    row["dissent_count"] = len(declarations)
                    row["false_dissent_count"] = sum(d["answer"] != correct for d in declarations)
                    if protocol in {"protected_dissent", "protected_dissent_review"}:
                        qualified = [result["declarations"][i] for i in result.get("qualifying_dissent_indices", [])]
                        row["qualifying_dissent_count"] = len(qualified)
                        row["false_qualifying_dissent_count"] = sum(d["answer"] != correct for d in qualified)
                rows.append(row)
    return manifest, rows, screening, audits


def descriptive(rows):
    groups = defaultdict(list)
    for row in rows:
        for scope in ("all", row["dataset"], row["dataset"] + "/" + row["family"]):
            groups[row["model_id"], scope, row["protocol"]].append(row)
    output = []
    for (model, scope, protocol), group in sorted(groups.items()):
        valid = [r for r in group if r["available"]]
        focus = [r for r in valid if r["initial_category"] == FOCUS]
        focus_scheduled = [r for r in group if r["initial_category"] == FOCUS]
        correct_count = sum(r["correct"] for r in valid)
        resolved = sum(r["resolved"] for r in valid)
        def average(field):
            values = [r[field] for r in valid if r[field] is not None]
            return sum(values) / len(values) if values and len(values) == len(valid) else None
        output.append({"model_id": model, "scope": scope, "protocol": protocol, "scheduled_panels": len(group),
                       "unique_questions": len({r["task_id"] for r in group}), "available_panels": len(valid), "missing_panels": len(group) - len(valid),
                       "accuracy_complete_cases": correct_count / len(valid) if valid else None,
                       "success_over_scheduled": correct_count / len(group), "coverage_over_scheduled": resolved / len(group),
                       "accuracy_when_resolved": correct_count / resolved if resolved else None,
                       "focus_scheduled": len(focus_scheduled), "focus_available": len(focus),
                       "minority_recovery": sum(r["correct"] for r in focus) / len(focus) if focus else None,
                       "minority_suppression": sum(r["suppression"] for r in focus) / len(focus) if focus else None,
                       "minority_agent_survival": sum(r["surviving_correct_agents"] for r in focus) / sum(r["initial_correct_agents"] for r in focus) if focus else None,
                       "false_dissent": sum(r["false_dissent_count"] for r in valid) / sum(r["dissent_count"] for r in valid) if sum(r["dissent_count"] for r in valid) else None,
                       "false_qualifying_dissent": sum(r["false_qualifying_dissent_count"] for r in valid) / sum(r["qualifying_dissent_count"] for r in valid) if sum(r["qualifying_dissent_count"] for r in valid) else None,
                       "escalation_rate": sum(r["escalated"] for r in valid) / len(valid) if valid else None,
                       "mean_calls": average("calls"), "mean_request_attempts": average("request_attempts"),
                       "mean_tokens": average("tokens"), "mean_cost_usd": average("cost_usd"), "mean_latency_seconds": average("latency_seconds"),
                       **{name: sum(r[name] for r in valid) for name in ("correct_to_correct", "correct_to_wrong", "wrong_to_correct", "wrong_to_wrong")}})
    return output


def contrasts(rows, plan):
    indexed = {(r["model_id"], r["seed"], r["task_id"], r["protocol"]): r for r in rows}
    output = []
    for model in sorted({r["model_id"] for r in rows}):
        model_results = []
        scopes = ["all"] + sorted({r["dataset"] for r in rows if r["model_id"] == model})
        for scope in scopes:
            for treatment, baseline in plan["comparisons"]:
                candidates = [r for r in rows if r["model_id"] == model and r["protocol"] == treatment and (scope == "all" or r["dataset"] == scope)]
                for endpoint in ("accuracy", "minority_recovery", "minority_suppression"):
                    eligible = [r for r in candidates if endpoint == "accuracy" or r["initial_category"] == FOCUS]
                    pairs = []
                    for row in eligible:
                        other = indexed[(model, row["seed"], row["task_id"], baseline)]
                        if row["available"] and other["available"]:
                            field = "suppression" if endpoint == "minority_suppression" else "correct"
                            pairs.append({"task_id": row["task_id"], "stratum": row["dataset"] + "/" + row["family"],
                                          "treatment": row[field], "baseline": other[field]})
                    result = paired_inference(pairs, plan["bootstrap_samples"], seed_for(plan["seed"], model, scope, treatment, baseline, endpoint))
                    result.update(model_id=model, scope=scope, treatment=treatment, baseline=baseline, endpoint=endpoint,
                                  eligible_panels=len(eligible), missing_pairs=len(eligible) - len(pairs),
                                  favorable_direction="negative" if endpoint == "minority_suppression" else "positive")
                    model_results.append(result)
        adjusted = holm_adjust([r["p_value"] for r in model_results])
        for row, p in zip(model_results, adjusted):
            row.update(p_holm=p, holm_family="all planned endpoint/scope contrasts within model", holm_family_size=sum(r["p_value"] is not None for r in model_results))
        output.extend(model_results)
    return output


def write_study_report(run, screen_only=False):
    run = Path(run)
    manifest, rows, screening, audits = materialize(run)
    write_jsonl(run / "screening.jsonl", screening)
    screening_counts = Counter((r["model_id"], r["seed"], r["dataset"], r["initial_category"]) for r in screening)
    screen_summary = [{"model_id": k[0], "seed": k[1], "dataset": k[2], "category": k[3], "panels": n} for k, n in sorted(screening_counts.items())]
    write_json(run / "screening_summary.json", screen_summary)
    if screen_only:
        return screen_summary
    if manifest.get("stage") != "deliberate" or manifest.get("status") == "running":
        raise ValueError("Complete or interrupt the deliberation stage before final reporting")
    tables = descriptive(rows)
    comparison = contrasts(rows, manifest["identity"]["statistics"])
    report = {"analysis_source_sha256": source_hash(), "synthetic": any(r["backend"] == "mock" for r in rows), "study_status": manifest["status"], "identity": manifest["identity"],
              "descriptive": tables, "contrasts": comparison, "resources": audits, "screening": screen_summary,
              "notes": ["Inferential comparisons use paired complete cases; missing pairs are explicit, never silently treated as wrong.",
                        "Success over scheduled panels counts missing decisions as unsuccessful; coverage is separate.",
                        "Bootstrap resamples questions within source/family strata, retaining all repetitions together.",
                        "Exact McNemar applies only to one observation per question; repeated panels use question-cluster sign flips with exchangeability assumptions.",
                        "Holm correction covers the planned contrasts across endpoints and source scopes within each model. Cross-model claims need a larger correction family.",
                        "Yoked controls match logical call counts, not tokens or actual retry expenditure.",
                        "Small strata and degenerate intervals are not evidence of certainty. Mock outputs are not empirical evidence."]}
    write_jsonl(run / "analysis_rows.jsonl", rows)
    write_json(run / "research_summary.json", report)
    lines = ["# Research study report", "", "**SYNTHETIC SOFTWARE VALIDATION — not empirical LLM evidence.**" if report["synthetic"] else "Live collection; inspect missingness and audit records before interpretation.", "",
             "| Model | Protocol | Available / scheduled panels | Success / scheduled | Focus available | Recovery | Suppression |", "|---|---|---:|---:|---:|---:|---:|"]
    def fmt(x):
        return "N/A" if x is None else f"{x:.3f}"
    for row in tables:
        if row["scope"] == "all":
            lines.append(f'| {row["model_id"]} | {row["protocol"]} | {row["available_panels"]}/{row["scheduled_panels"]} | {fmt(row["success_over_scheduled"])} | {row["focus_available"]} | {fmt(row["minority_recovery"])} | {fmt(row["minority_suppression"])} |')
    lines += ["", *["- " + note for note in report["notes"]], "", "Full paired effects, intervals, adjusted p-values and resource accounting are in research_summary.json and the reporting notebook.", ""]
    (run / "research_report.md").write_text("\n".join(lines), encoding="utf-8")
    return report
