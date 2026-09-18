"""Research controls layered over the fixed four-condition pilot."""

from .common import canonical, seed_for
from .protocols import (BASE_SCHEMA, PROTOCOLS, SYSTEM, blind_argument, public_response,
                        run_task, shuffled_peers, strict_majority)

CONTROLS = ("independent_revision", "explicit_dissent", "reminder_revision", "extra_round_control", "independent_review_control")
RESEARCH_PROTOCOLS = PROTOCOLS + CONTROLS

INSTRUCTIONS = {
    "independent_revision": "Reassess your own original answer independently, using only the problem and your original justification. Keep or revise it. " + BASE_SCHEMA,
    "explicit_dissent": 'Before closure, reconsider your original and current answers. Choose AGREE or DISSENT regarding the proposal. You may restore your original position. Dissent must identify an alternative, the disputed claim, and evidence. Dissent has no power to delay closure or trigger review. Your answer is your final vote. Return base fields plus "stance" (AGREE or DISSENT), "disputed_claim" (string), "evidence" (string; use empty strings for agreement). ' + BASE_SCHEMA,
    "reminder_revision": "Reassess the proposed answer using your original answer, current answer and peer arguments. Keep or revise your answer on the merits. Your answer is your final vote. " + BASE_SCHEMA,
    "neutral_checkpoint": "Check the proposed answer against the problem, your original answer, current answer, and peer arguments. Return your assessment. This is a scheduled checkpoint, not a vote or a request for escalation. " + BASE_SCHEMA,
    "extra_round": "Conduct an additional scheduled reconsideration of the problem and the checkpoint arguments. Cast your final answer. " + BASE_SCHEMA,
    "review_control": 'Independently solve the original problem and check the supplied proposed argument. Choose any original option, or UNRESOLVED if you cannot justify an answer. You have no prior conversation. ' + BASE_SCHEMA + ' UNRESOLVED is also allowed.',
}


def independent_panel(task, config, store):
    from .protocols import messages_for
    return [store.call(f"{task['task_id']}/independent/{i}", "independent", task, {}, messages_for("independent", task, {})) for i in range(5)]


def stopped_result(task, initial, protocols):
    ids = [f"{task['task_id']}/independent/{i}" for i in range(5)]
    return {"task_id": task["task_id"], "initial": initial, "debate": initial, "proposal": strict_majority(initial),
            "declarations": [], "qualifying_dissent_indices": [], "selected_dissent_index": None, "review": None,
            "controls": {}, "protocols": {p: {"final_answer": strict_majority(initial), "final_panel": initial,
            "call_ids": ids[:], "deliberation_rounds": 0, "escalated": False, "review_calls": 0,
            "decision_rule": "unanimity_stop"} for p in protocols}}


def run_research_task(task, config, store):
    result = run_task(task, config, store)
    initial, revised, proposal = result["initial"], result["debate"], result["proposal"]
    task_id = task["task_id"]
    base_calls = result["protocols"]["standard_debate"]["call_ids"]
    control_records = {}

    def ask(kind, i, context):
        cid = f"{task_id}/{kind}/{i}"
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": INSTRUCTIONS[kind] + "\n" + canonical({"problem": {"question": task["question"], "options": task["options"]}, "context": context})}]
        return cid, store.call(cid, kind, task, context, messages)

    def save(name, panel, ids, rounds, final=None, reviewed=False, escalated=False):
        result["protocols"][name] = {"final_answer": final if reviewed else strict_majority(panel), "final_panel": panel,
                                    "call_ids": ids, "deliberation_rounds": rounds, "review_calls": int(reviewed),
                                    "escalated": escalated, "decision_rule": "independent_review" if reviewed else "strict_majority"}

    ids = result["protocols"]["majority_vote"]["call_ids"][:]
    panel = []
    for i in range(5):
        cid, reply = ask("independent_revision", i, {"own": public_response(initial[i])})
        ids.append(cid)
        panel.append(reply)
    save("independent_revision", panel, ids, 1)
    control_records["independent_revision"] = panel

    checkpoints = {}
    checkpoint_ids = {}
    for kind in ("explicit_dissent", "reminder_revision", "neutral_checkpoint"):
        panel, ids = [], base_calls[:]
        if proposal is not None:
            for i in range(5):
                context = {"original": public_response(initial[i]), "current": public_response(revised[i]),
                           "own": public_response(revised[i]), "proposal": proposal,
                           "peers": shuffled_peers(revised, i, seed_for(config.seed, task_id, "dissent-order", i)),
                           "confidence_threshold": config.dissent_threshold}
                cid, reply = ask(kind, i, context)
                ids.append(cid)
                panel.append(reply)
        else:
            panel = revised
        checkpoints[kind], checkpoint_ids[kind] = panel, ids
        control_records[kind] = panel if proposal is not None else []
        if kind != "neutral_checkpoint":
            save(kind, panel, ids, 1 + int(proposal is not None))

    triggered = bool(result["qualifying_dissent_indices"])
    panel = revised
    ids = checkpoint_ids["neutral_checkpoint"][:]
    if triggered:
        panel = []
        for i in range(5):
            context = {"own": public_response(checkpoints["neutral_checkpoint"][i]), "proposal": proposal,
                       "peers": shuffled_peers(checkpoints["neutral_checkpoint"], i, seed_for(config.seed, task_id, "reconsider-order", i))}
            cid, reply = ask("extra_round", i, context)
            ids.append(cid)
            panel.append(reply)
    save("extra_round_control", panel, ids, 1 + int(triggered), escalated=triggered)
    ids = checkpoint_ids["neutral_checkpoint"][:]
    if triggered:
        source = next((r for r in initial if r["answer"] == proposal), next(r for r in revised if r["answer"] == proposal))
        cid, review = ask("review_control", 0, {"proposed_argument": blind_argument(source)})
        ids.append(cid)
        final = None if review["answer"] == "UNRESOLVED" else review["answer"]
        control_records["review_control"] = review
        save("independent_review_control", revised, ids, 1, final, True, True)
    else:
        save("independent_review_control", revised, ids, 1)
    result["controls"] = control_records
    return result
