"""Ground truth enters only here, after deliberation has finished."""

import math
from collections import Counter

from .protocols import PROTOCOLS, strict_majority


def rate(numerator, denominator):
    if not denominator:
        return {"numerator": numerator, "denominator": 0, "value": None, "wilson_95": None}
    p = numerator / denominator
    z = 1.959963984540054
    scale = 1 + z * z / denominator
    center = (p + z * z / (2 * denominator)) / scale
    margin = z * math.sqrt(p * (1 - p) / denominator + z * z / (4 * denominator**2)) / scale
    return {"numerator": numerator, "denominator": denominator, "value": p, "wilson_95": [max(0, center - margin), min(1, center + margin)]}


def category(initial, correct):
    majority = strict_majority(initial)
    answers = [r["answer"] for r in initial]
    if len(set(answers)) == 1:
        return "unanimous_correct" if majority == correct else "unanimous_wrong"
    if majority is None:
        return "no_strict_majority"
    if majority == correct:
        return "majority_correct_minority_wrong"
    if correct in answers:
        return "majority_wrong_minority_correct"
    return "majority_wrong_no_correct_agent"



def classify_initial_panels(results, gold):
    """Auditable answer-label classification, not a judgment of reasoning quality."""
    rows = []
    for result in results:
        task_id = result["task_id"]
        answers = [r["answer"] for r in result["initial"]]
        correct = gold[task_id]
        rows.append({"task_id": task_id, "initial_answers": answers,
                     "correct_answer": correct, "answer_counts": dict(Counter(answers)),
                     "correct_agent_indices_zero_based": [i for i, a in enumerate(answers) if a == correct],
                     "initial_majority_answer": strict_majority(result["initial"]),
                     "initial_category": category(result["initial"], correct)})
    return rows


def costs(records):
    attempts = [a for r in records for a in r.get("attempts", [r])]
    result = {"calls": len(records), "request_attempts": len(attempts), "retries": len(attempts) - len(records), "latency_seconds_sum": sum(r.get("latency_seconds", 0) for r in records)}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens", "cost"):
        values = [r.get("usage", {}).get(field) for r in attempts]
        known = [x for x in values if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)]
        result[field] = sum(known) if len(known) == len(values) else None
        result[field + "_known_subtotal"] = sum(known)
        result[field + "_missing_calls"] = len(values) - len(known)
    return result


def analyze(tasks, gold_rows, results, records, backend):
    gold = {}
    for row in gold_rows:
        if row["task_id"] in gold:
            raise ValueError("Duplicate gold task ID")
        gold[row["task_id"]] = row["correct_answer"]
    task_map = {task["task_id"]: task for task in tasks}
    if set(gold) != set(task_map):
        raise ValueError("Answer key must cover exactly the task dataset")
    if any(gold[k] not in task_map[k]["options"] for k in gold):
        raise ValueError("Gold answer is not an option label")
    ids = [r["task_id"] for r in results]
    if len(ids) != len(set(ids)) or set(ids) != set(task_map):
        raise ValueError("Analysis requires exactly one completed result per task")
    categories = {r["task_id"]: category(r["initial"], gold[r["task_id"]]) for r in results}
    focus = [r for r in results if categories[r["task_id"]] == "majority_wrong_minority_correct"]
    report = {"backend": backend, "synthetic": backend == "mock", "tasks": len(results),
              "initial_categories": dict(Counter(categories.values())), "focus_prevalence": rate(len(focus), len(results)),
              "physical_cost": costs(list(records.values())), "protocols": {}, "paired_vs_standard_debate": {}}
    for name in PROTOCOLS:
        transitions = Counter({"correct_to_correct": 0, "correct_to_wrong": 0, "wrong_to_correct": 0, "wrong_to_wrong": 0})
        minority_survivors = minority_total = 0
        any_survivors = suppression = recovery = focus_incorrect = 0
        for row in results:
            correct = gold[row["task_id"]]
            outcome = row["protocols"][name]
            for before, after in zip(row["initial"], outcome["final_panel"], strict=True):
                first = "correct" if before["answer"] == correct else "wrong"
                second = "correct" if after["answer"] == correct else "wrong"
                transitions[first + "_to_" + second] += 1
            if categories[row["task_id"]] == "majority_wrong_minority_correct":
                minority = [i for i, r in enumerate(row["initial"]) if r["answer"] == correct]
                surviving = sum(outcome["final_panel"][i]["answer"] == correct for i in minority)
                minority_total += len(minority)
                minority_survivors += surviving
                any_survivors += surviving > 0
                recovery += outcome["final_answer"] == correct
                final = outcome["final_answer"]
                focus_incorrect += final is not None and final != correct
                panel_answers = {r["answer"] for r in outcome["final_panel"]}
                suppression += final is not None and final != correct and panel_answers == {final}
        outcomes = [r["protocols"][name] for r in results]
        covered = sum(o["final_answer"] is not None for o in outcomes)
        correct_count = sum(r["protocols"][name]["final_answer"] == gold[r["task_id"]] for r in results)
        declarations = [d for r in results for d in r["declarations"] if d["stance"] == "DISSENT"] if name in PROTOCOLS[2:] else []
        false_dissent = sum(d["answer"] != gold[r["task_id"]] for r in results for d in r["declarations"] if d["stance"] == "DISSENT") if name in PROTOCOLS[2:] else 0
        eligible = [(r, r["declarations"][i]) for r in results for i in r["qualifying_dissent_indices"]] if name in PROTOCOLS[2:] else []
        call_ids = [cid for o in outcomes for cid in o["call_ids"]]
        if len(call_ids) != len(set(call_ids)):
            raise ValueError("Duplicate call in protocol cost accounting")
        report["protocols"][name] = {
            "accuracy": rate(correct_count, len(results)), "coverage": rate(covered, len(results)),
            "accuracy_when_resolved": rate(correct_count, covered), "unresolved": len(results) - covered,
            "correct_minority_recovery": rate(recovery, len(focus)),
            "correct_minority_suppression": rate(suppression, len(focus)),
            "focus_wrong_final_answer": rate(focus_incorrect, len(focus)),
            "correct_minority_agent_survival": rate(minority_survivors, minority_total),
            "correct_minority_task_survival": rate(any_survivors, len(focus)),
            "agent_transitions": dict(transitions),
            "false_dissent": rate(false_dissent, len(declarations)),
            "false_qualifying_dissent": rate(sum(d["answer"] != gold[r["task_id"]] for r, d in eligible), len(eligible)),
            "escalation": rate(sum(o["escalated"] for o in outcomes), len(results)),
            "deliberation_rounds_total": sum(o["deliberation_rounds"] for o in outcomes),
            "review_calls": sum(o["review_calls"] for o in outcomes),
            "standalone_cost": costs([records[cid] for cid in call_ids]),
        }
        if name != "standard_debate":
            wins = losses = 0
            for row in results:
                correct = gold[row["task_id"]]
                treatment = row["protocols"][name]["final_answer"] == correct
                baseline = row["protocols"]["standard_debate"]["final_answer"] == correct
                wins += treatment and not baseline
                losses += baseline and not treatment
            report["paired_vs_standard_debate"][name] = {"wins": wins, "losses": losses, "ties": len(results) - wins - losses,
                                                         "accuracy_difference": (wins - losses) / len(results)}
    return report


def render_report(report):
    def percent(metric):
        return "N/A (0 eligible)" if metric["value"] is None else f'{metric["value"]:.1%} ({metric["numerator"]}/{metric["denominator"]})'

    lines = ["# Pilot report", ""]
    if report["synthetic"]:
        lines += ["**SYNTHETIC SOFTWARE TEST — these results are not empirical LLM findings.**", ""]
    lines += [f'Tasks: {report["tasks"]}. Initial majority-wrong/minority-correct prevalence: {percent(report["focus_prevalence"])}.', "",
              "| Protocol | Accuracy | Recovery | Wrong consensus / suppression | Coverage | Calls (standalone) |",
              "|---|---:|---:|---:|---:|---:|"]
    for name, row in report["protocols"].items():
        lines.append(f'| {name} | {percent(row["accuracy"])} | {percent(row["correct_minority_recovery"])} | {percent(row["correct_minority_suppression"])} | {percent(row["coverage"])} | {row["standalone_cost"]["calls"]} |')
    lines += ["", "Recovery and suppression are conditional on an initially wrong strict majority with at least one correct agent. Suppression requires all five final panel answers and the final decision to agree on the same wrong answer. A wrong majority decision alone is reported separately in summary.json.", "",
              "Panel transitions exclude the independent reviewer. A successful appeal can improve the final decision without restoring any panel member's answer. Survival is measured by correctness, not continued use of the DISSENT label.", "",
              "Accuracy counts unresolved outcomes as unsuccessful; coverage and accuracy among resolved outcomes are separate. JSON rates include numerator, denominator, and descriptive Wilson 95% intervals. Agent-level intervals do not adjust for within-task dependence.", "",
              f'Physical calls across the paired experiment: {report["physical_cost"]["calls"]}. Shared calls are charged to every protocol that uses them for standalone comparison. Missing cost/token data remain null, never zero. Latency is the sum of serial call durations, not a simulated parallel deployment latency.', "",
              "This pilot cannot establish a causal social-pressure effect: additional computation, dissent prompting, and original-answer reminders are confounded with the mechanism. Add matched-cost and independent-revision controls before confirmatory claims. Small or empty focus strata are inconclusive.", ""]
    return "\n".join(lines)
