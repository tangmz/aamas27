> Historical four-condition pilot specification. For the current staged research runner, retry policy, controls, and statistics, see [research-workflow.md](research-workflow.md).

# Pilot protocol and analysis specification

This document fixes implementation choices for a feasibility pilot. It is not a registered confirmatory analysis plan or a claim of novelty. The source code and prompts are hashed in each run manifest.

## Units, pairing and data

The unit of the paired protocol comparison is a question with one sampled five-agent initial panel. Use all 50 questions for unconditional accuracy and prevalence; do not select questions using treatment outcomes. Initial M−m+ classification uses the answer key only during post-hoc analysis. It is identical for all conditions because they share the initial panel.

Fresh questions comprise 17 ordering tasks, 17 Boolean tasks, and 16 shortest-path tasks under the default configuration. Ordering counts use enumeration and subset dynamic programming; Boolean counts use truth-table evaluation and assignment-set algebra; shortest paths use Dijkstra and enumeration of simple paths. Distractors are unique numeric alternatives and option positions are shuffled. Difficulty is exploratory, not calibrated; these tasks may be too easy or otherwise unrepresentative for a selected model. Fresh generation reduces verbatim benchmark overlap but cannot guarantee unfamiliar task structures.

All agent calls use one model/provider and the same inference settings. Initial calls see only the problem. Revisions are simultaneous in the informational sense: every agent sees a snapshot of the previous round, never another agent's newly revised answer. Calls execute serially for auditability. Peer positions are seeded and independently shuffled for each recipient; identities are omitted, while multiplicity remains visible to panel members as part of the social treatment. Review candidates are separately shuffled and counts are omitted.

Each response supplies an option label, brief justification and confidence. No private chain-of-thought transcript is requested. The runner is given only the public task file; neither selection of dissent nor any closure decision can access gold labels.

## Classification

A majority is a single option held by at least three of five agents. A 2–2–1 or 2–1–1–1 distribution is a no-strict-majority case, even if a plurality exists. Report these separately.

Initial categories are unanimous correct, unanimous wrong, majority correct/minority wrong, majority wrong/minority correct (M−m+), majority wrong/no correct agent, and no strict majority. M−m+ requires a wrong strict majority and at least one individually correct answer. All protocols process all questions; the focus stratum is defined once from the shared initial answers during analysis.

## Closure and dissent

The common debate yields a proposal only if it has a strict majority. Otherwise all three deliberative protocols return unresolved and do not run a closure checkpoint. The independent baseline retains its initial decision.

Before either protected branch closes, every agent sees its original response, its debate response, the other revised arguments, and the proposed option. It returns AGREE or DISSENT with an answer, disputed claim, evidence and confidence. AGREE responses do not re-vote; an unqualified DISSENT has no procedural effect. This checkpoint is itself an intervention and must be controlled in a later mechanism-isolation study.

Qualifying dissent is a syntactic and confidence gate, not an oracle: DISSENT, a different valid option, nonempty disputed claim and evidence, and confidence >= threshold (default 0.6). Gate string fields are not checked for semantic validity. Confidence is self-reported and uncalibrated. The highest confidence qualifying alternative is selected, with a seeded tie break independent of gold. Incorrect high-confidence dissent can therefore win; false dissent and selected dissent remain auditable.

Protected dissent triggers one simultaneous reconsideration round for all five members, whose strict majority then determines the answer. It does not allow indefinite vetoes. The appeal branch instead gives a fresh stateless reviewer two arguments and binding authority. It does not run the extra group round first. The reviewer is restricted to those two options or UNRESOLVED; it is not counted as a sixth voter. Panel survival metrics in the appeal condition refer to the last five-member panel (the debate snapshot), not to the reviewer's binding decision.

The reviewer receives no explicit side labels, counts, identities, confidence or history. One initial supporting rationale is preferred for the proposal. The alternative argument consists of the selected disputed claim and evidence. A lexical sentence filter removes common social references; it cannot establish perfect semantic blindness and can remove substantive content. Archive and audit the precise resulting inputs. Candidate argument-source asymmetry is also a limitation to address in stronger experiments.

## Metrics

All rate outputs contain numerator, denominator, value, and a descriptive Wilson 95% interval. Empty denominators produce null values and intervals. No correctness labels affect the protocol.

| Metric | Numerator | Denominator |
|---|---|---|
| Accuracy | Correct final decisions | All tasks |
| Coverage | Non-unresolved final decisions | All tasks |
| Accuracy when resolved | Correct final decisions | Resolved tasks |
| Focus prevalence | Initial M−m+ tasks | All tasks |
| Correct-minority recovery | Correct final decisions on M−m+ | Initial M−m+ tasks |
| Correct-minority suppression | Wrong final answer also unanimously held by the final panel | Initial M−m+ tasks |
| Focus wrong final answer | Wrong non-unresolved final answer, with or without unanimity | Initial M−m+ tasks |
| Correct-minority agent survival | Initially correct focus agents still correct in final panel | Initially correct focus agents |
| Correct-minority task survival | At least one initially correct agent still correct in final panel | Initial M−m+ tasks |
| False dissent | DISSENT declarations proposing a wrong alternative | All DISSENT declarations |
| False qualifying dissent | Qualifying declarations proposing a wrong alternative | All qualifying declarations |
| Escalation | Tasks with a selected qualifying dissent | All tasks |

Strict suppression operationalizes “incorrect consensus” as unanimous agreement on a wrong final decision. It is deliberately narrower than a wrong final majority decision. A wrong majority already exists at baseline for every focus case, so calling all wrong final votes suppression would conflate absence of recovery with loss of the correct position. Agent transitions and survival expose non-unanimous losses too.

Track correct→correct, correct→wrong, wrong→correct, and wrong→wrong for each original panel member, comparing the initial answer with the protocol's last panel response. These are descriptive transitions. Correct→wrong alone does not prove a social mechanism: independent stochastic revision could cause the same change. Agent-level Wilson intervals ignore within-question correlation and must not be used as independent-agent inferential evidence.

Unresolved outcomes count as unsuccessful on unconditional accuracy; they are neither incorrect consensus nor recovery. Reporting coverage alongside conditional accuracy prevents an abstaining method from appearing artificially accurate. Paired accuracy wins/losses/ties against standard debate are descriptive, with each task counted once. The implementation makes no significance or novelty claims; a later study should pre-specify paired inference, task-level resampling, repeated samples and multiplicity handling.

## Resources and reproducibility

Physical calls are deduplicated across shared prefixes. Logical standalone counts are 5 for majority, 10 for debate, 10–20 for protected dissent and 10–16 for appeal. If a proposal exists and no dissent qualifies, protected conditions use 15 calls. The upper bound across all four branches is 21 per task, not the sum of standalone counts. Tokens and reported API cost follow the same allocation. The summary includes sum of serial request latencies, deliberation rounds, and review calls. Declaration checkpoints are calls but not counted as deliberation rounds.

Each call records exact prompts, requested model/provider, returned model/provider when available, inference settings, per-call derived seed and whether it was sent, timestamps, full response, usage and local elapsed time. Raw response metadata can retain reasoning-token details. Missing usage remains unknown. Pin model versions and provider before collection; hosted weights and backend behavior can still change.

Calls are journaled, fail-fast, and never automatically retried. Interrupted or failed runs are not scored as completed experiments. They must remain visible in the audit trail and be disclosed in empirical reporting. Resume permits call-cap interruptions with unchanged experimental identity; ambiguous pending calls and failed calls require inspection and a new run rather than silent replacement. API credentials are read from environment only and are not part of records.

## Decision after the pilot

First inspect initial-state prevalence, valid completion rates, task difficulty and support-count leakage in reviewer inputs. Report exact relevant counts and intervals. If M−m+ is sparse, expand naturally sampled tasks or run a separately labelled controlled pressure experiment built from genuine model outputs. Do not pool constructed teams with natural-prevalence estimates.

Before attributing benefits to protected dissent, add explicit unprotected dissent, original-answer reminder, independent revision, and matched-cost extra-round/review controls. Broader experiments can then add model families, heterogeneous teams, public benchmarks, dissent representations and task-scale variation. The 50-task mock run validates software only; a live pilot is necessary to establish whether the proposed phenomenon occurs at a useful frequency.
