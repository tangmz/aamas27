# Assessment of study-01

Assessment date: 2026-10-03. No new model calls were made for this assessment.

## Decision

The current evidence does not support a full empirical paper claiming that protected dissent prevents premature consensus or improves decisions. Keep this run as a feasibility experiment showing a pronounced ceiling effect for this model/task combination. A negative result could be publishable, but this run contains almost no opportunities to test the intended mechanism and no actual escalations. It is not an equivalence study and does not establish that protected dissent is ineffective in general.

## What was collected

The recorded model is `deepseek/deepseek-v4.1-flash`, served by Together through OpenRouter. All 9,970 logical call journals identify that resolved model and provider. There are 600 unique questions (300 BBH, 300 generated), three repetitions, and five agents per panel. The run schedules 1,800 panels; repetitions are not independent new questions. `send_seed` is false, so the recorded seeds control orchestration rather than a provider-guaranteed sampling seed.

The collection status is `complete_with_failures`: 1,789 complete panels, nine initial collection failures, and two deliberation failures. There are 9,980 physical request attempts. Known reported cost is $8.006713644; eight logical call records have incomplete cost accounting, so this is not a verified invoice total or account balance.

## Screening and mechanism exposure

| Initial category | BBH | Generated | Total |
|---|---:|---:|---:|
| Unanimous correct | 892 | 865 | 1,757 |
| Correct majority, wrong minority | 7 | 26 | 33 |
| Wrong majority, correct minority | 1 | 0 | 1 |
| Initial panel unavailable | 0 | 9 | 9 |

Only 34 panels disagreed (31 unique questions), and 32 of those completed every protocol. Under the frozen disagreement-only selection policy, the 1,757 initially unanimous panels were stopped and their decisions reused across all conditions. They did not independently undergo nine deliberation procedures.

Among complete panels there were zero dissent declarations, zero qualifying dissent events, zero escalations, and zero correct-to-wrong transitions under standard debate. Across all journals there were no reconsideration, appeal-review, extra-round, or control-review calls. The new procedural rights therefore were never exercised.

The one wrong-majority/correct-minority case was BBH logical deduction five objects item 0165, repetition 2028. The gold answer was D. Initial answers were D,E,E,D,E; standard debate changed these to D,D,D,D,D. Dissent declarations all answered D and no appeal was triggered. Independent revision also produced a correct team decision. This example supports ordinary correction, not a distinctive benefit of dissent protection.

## Outcomes and inference

Majority voting was correct on 1,790/1,791 available panels (99.944%). Each of the eight other conditions was correct on 1,789/1,789 available panels (100%). Their operational success rate was 1,789/1,800 (99.389%), with missingness explicitly included in the denominator. These figures must not be conflated.

All seven planned overall accuracy comparisons had zero wins, zero losses, an observed difference of zero, and adjusted p=1. Minority recovery had only one eligible panel. The plotted [0,0] bootstrap intervals arise because every observed paired difference is zero; they do not demonstrate population equivalence or perfect certainty. Source-specific generated-data recovery is undefined because its focus denominator is zero. The displayed 100% recovery on BBH is 1/1, not a robust effect estimate.

## Integrity and remaining data issues

Read-only reconstruction through `dissent.reporting.materialize` passed task/key and call-reference integrity checks. The current source hash matches the collection source hash. Reconstructed rows match saved substantive outcomes and counts; differences were confined to floating-point cost accumulation at approximately machine precision.

The 11 terminal call failures comprise eight responses rejected by the exact required-key schema and three `finish_reason=error` responses. They were not terminal token-limit failures. Two earlier attempts had `finish_reason=length`, with their logical calls subsequently succeeding. Preserve the original strict analysis. A separately labelled sensitivity analysis can examine deterministic extraction of already returned answers, but must apply a gold-blind rule to every affected response and must not silently replace the original results. Some missing agent responses were never collected, so offline extraction cannot complete all failed panels.

The task result is committed after all branches finish; a later control failure can therefore leave earlier successful branch calls in journals while the table marks their outcomes unavailable. Reconstructing those existing branch outcomes is a possible offline sensitivity analysis, not a reason to spend on rerunning everything. None of these missingness issues resolves the central lack of dissent events.

## Defensible claim and next decision

A defensible statement is: 'For this model, on the selected 600 structured reasoning questions with three repetitions and unanimity stopping, majority voting was near ceiling. Initial disagreement occurred in 34/1,791 available panels, only one panel had a correct minority against a wrong majority, and protected-dissent escalation was never exercised. These conditions were insufficient to evaluate the benefit of procedural dissent protection.'

Keep the frozen run, journals and source version. Do not rerun the same design or increase repetitions merely to obtain significance. Before any further paid collection, use separate development tasks to calibrate difficulty and verify that disagreements and procedural escalations actually occur. A follow-up would need harder tasks or a different model, a smaller justified set of comparisons, explicit budgets, and an analysis plan fixed before observing treatment effects. Constructed majority-pressure experiments are another possible follow-up, but measure behaviour under imposed disagreement rather than natural prevalence and must be labelled accordingly. The present run should remain disclosed when reporting a revised design.

With no additional budget, prepare a transparent feasibility report or thesis section; a full AAMAS empirical effectiveness submission is not supported by this evidence alone. A workshop or position-paper direction would need its own substantive contribution and venue fit; acceptance is not implied.

## Initial literature positioning

This was a targeted literature check, not a systematic novelty review. Compare the proposal explicitly with [Voting or Consensus? Decision-Making in Multi-Agent Debate](https://aclanthology.org/2025.findings-acl.606/), which studies decision protocols, and [Free-MAD: Consensus-Free Multi-Agent Debate](https://arxiv.org/abs/2509.11035), which addresses consensus-free debate. The distinct contribution would need to be a well-specified, evaluated procedural right, not the general observation that agreement may be undesirable.

The [AAMAS 2027 reviewer guidelines](https://warwick.ac.uk/fac/sci/dcs/aamas2027/guidelines-and-policies/reviewer-guidelines/) also make authors responsible for validating AI-assisted content. This assessment is research advice to the authors, not a conference review or acceptance prediction.
