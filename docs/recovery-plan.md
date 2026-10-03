# Research recovery plan — 3 October 2026

## Submission route

The author reports that no main-track abstract was registered. The official main-track deadline was 1 October; full papers are due 8 October. Do not assume eligibility without an explicit exception from the chairs. No email or submission has been sent.

The actionable target is **AAMAS 2027 Blue Sky Ideas**: author OpenReview registration 20 October, abstract 5 November, paper 12 November (all deadlines end of day UTC−12). It is a four-page vision-paper track with additional reference pages. It requires a Blue Sky rationale and a separate chair-only author-background statement. It is not a fallback guarantee of acceptance. Sources: [main track](https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/call-for-main-track/), [Blue Sky](https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/call-for-blue-sky-ideas/), [instructions](https://warwick.ac.uk/fac/sci/dcs/aamas2027/guidelines-and-policies/instructions/).

## Proposed thesis

**An agent's change of endorsement should not automatically cancel the institutional standing of an unresolved registered challenge.** The proposed controller separates current answers from obligations to adjudicate before resolved closure. This is a research direction connecting LLM orchestration to established social commitments, not a claim to have invented commitments or proven a new accuracy result.

Working title: *The Right to Dissent After Agreement: Persistent Challenges for Accountable Agent Decisions*.

Completed study-01 becomes a candid motivating feasibility study. It demonstrates a ceiling effect and absent mechanism activation in this particular setup. It does NOT empirically demonstrate endorsement erasure, minority suppression, or superiority of the proposed persistent protocol.

## Completed actions

- Reconstructed study-01 from journals, preserving the run and all failures.
- Audited primary literature and identified substantial overlap (see novelty-review.md).
- Built an offline pool of 31 question-level pairs from authentic saved independent responses; 62 count-swapped scenarios; nine development questions and 22 evaluation questions.
- Kept gold keys separate from public stimuli and recorded source journal/content hashes.
- Implemented a small challenge-lifecycle controller and prompt-plan compiler outside the frozen dissent package.
- Added focused tests for persistence, expiry, capacity exhaustion, review blinding, and the possibility of harm.
- Prepared an anonymous official-template paper draft, reference list, submission text, and AI-assistance disclosure.

## What the offline pack is and is not

Each question has one correct and one incorrect archived argument, selected by a fixed provenance-hash ranking, not by persuasiveness. Stated support is swapped between 4:1 and 1:4; the argument strings are held fixed. The counts are hypothetical. No claim is made that five independent agents produced these two compressed arguments in those counts.

The pool was selected after examining pilot correctness and is a **post hoc, enriched diagnostic population**. It is not a new representative evaluation set. Twenty-two of its 31 questions are Boolean. All task variants remain in the same split. Gold is used to construct and score this controlled benchmark, not exposed to decision agents. The population selection must be disclosed.

Manual review fields are pending in runs/recovery-01/manual_review.jsonl. Review for ambiguity, accidental social cues, coherent reasoning, and answer/argument mismatch before any live use. Gold-blind presentation to the reviewer is preferred for argument-quality annotation. Do not exclude items because they make a treatment look bad. Record every exclusion and apply the frozen rule consistently.

## Future experiment specification (not collected)

Four logical requests per scenario: ordinary closure; explicit checkpoint given that saved closure; neutral recheck of the closure with both arguments; independent count-blind assessment of both arguments. Requests and outputs must be saved. Randomize execution order of independent branches and candidate order by a frozen seed, counterbalanced across support swaps.

Replay six decisions from those responses: ordinary, explicit checkpoint, neutral review, current-objection-triggered review, persistent review, and unconditional review. Reactive review triggers on a changed valid answer with confidence at least 0.6; persistent review invokes the archived challenge. This simplified replay gate is a new diagnostic definition, not the identical study-01 qualifying-dissent schema. Freeze it and its rationale before collection.

Primary estimand: paired change in correct final decisions for persistent versus reactive policy within the controlled population. Separate estimands: review exposure after endorsement change, harmful overturns with a correct majority, and operational unresolved/failure rates. Report effect sizes and intervals clustered by question, not 62 independent samples. Repeated attempts are not new observations. Count swaps manipulate declared support, not latent social beliefs.

Compare against explicit checkpoint and neutral review as secondary endpoints with an explicit multiplicity family. Include the unconditional reviewer even when it is identical to persistent review: in an all-disagreement sample this equality is structural. A benefit over reactive review alone may be a benefit of additional review; it does not establish a unique institutional mechanism. For stronger identification, add ordinary no-challenge episodes and compare allocation under matched budgets, and hold reviewer inputs fixed when changing authority. A factorial extension can separate information blinding from authority. Rights announced in advance require separate fresh trajectories; paired policy replay holds behaviour fixed.

This small pool has no demonstrated power. Development is for assessing exposure and failures, not selecting a design because its effect is positive. If development has no decision variation or no difference in review exposure, stop that efficacy experiment. Retain a vision-paper contribution with the limitation disclosed, or redesign on new development material. Do not silently relabel evaluation cases as development after seeing treatment effects.

## Budget

No new paid collection is authorized by this recovery package. The completed run's known cost is $8.0067, with incomplete usage on eight calls and possible earlier preflight spending. This does not establish a $1.9933 remaining account balance.

The candidate plan has 72 development requests and 248 requests for all scenarios at four per scenario, before retries. Applying the old per-attempt mean yields about $0.20 for all 248; applying the old 95th-percentile attempt cost yields about $0.47. These are arithmetic scenarios, NOT a price quote, upper bound, confidence interval, or guarantee: paired arguments change prompt sizes and responses, and the historical sample contains unusually long responses. Check actual balance and pricing and use a declared spending cap/reserve before any live work. A Blue Sky draft can proceed without collecting this extension.

## Concrete schedule

1. By 10 October: author and supervisor read the draft, challenge the novelty comparison, and decide whether the vision is credible. Check institutional grounding and whether another contribution is needed.
2. By 17 October: complete the argument audit and revise the lifecycle assumptions; decide whether to collect the small development extension. Do not commit the remaining credit before that decision.
3. By 20 October: all authors register their OpenReview accounts for the Blue Sky deadline. Complete factual author-background details.
4. Before 5 November: register the reviewed abstract and selected author list; preserve an immutable version of the design and artifacts.
5. Before 12 November: validate four-page body, references, anonymity, required statements, AI provenance, and final claims; submit only after author/supervisor approval.

Submission, author registration, and external communications remain author actions. No account action, submission, or message has been performed.

## Run the offline artifacts

```powershell
python -m recovery.audit --run runs/study-01 --out runs/recovery-new
python -m recovery.replay --pack runs/recovery-new --out runs/recovery-new-prompts
python -m unittest tests.test_recovery -v
```

Use a new output directory because candidate packs are immutable. The already-built pack is runs/recovery-01. No command above accesses OpenRouter. Generated data retain source-task licensing obligations; do not treat the original BBH questions as newly authored material.

## Remaining acceptance-critical gaps

No evidence yet that persistent standing improves LLM decisions; no systematic exhaustive novelty review; a small, selected replay pool; no measured reviewer reliability; no human verification of candidate argument quality; and no final supervisor review. These are visible limitations, not items to hide through framing. The vision must stand on a substantive institutional research agenda and clearly bounded formal claims. The current controller is illustrative, not production middleware or comprehensive formal verification.
