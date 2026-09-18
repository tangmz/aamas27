# Research workflow and analysis specification

This document specifies the current implementation. The older `pilot-design.md` describes the original four-condition feasibility pilot; use this document for staged studies and inferential reporting.

## Frozen design and units

The prepared dataset contains 300 BBH questions and 300 fresh procedurally generated questions. Reference option labels support deterministic answer scoring. Public labels are validated for mapping/format but are not all independently re-solved. Generated labels are checked by two exact algorithms. The sample is frozen before evaluating treatments. Use disjoint development questions to select model settings, prompts, difficulty and thresholds. Report source/family effects separately because task formats and numbers of answer options differ.

The observational unit is a question with a five-agent initial panel for one model and one repetition seed. Multiple models are separate homogeneous-team experiments. The configuration names all seeds, sources, inference/retry settings, policies and statistical comparisons before collection. Each unit uses the same question set and runs the same paired branches. Protocol branches share the initial panel and, when applicable, the common first debate and protected checkpoint.

Every initial response is sampled independently with no peer input. Calls are serial, but revision rounds are simultaneous in the information available: no response from a new round is visible to another member of that round. Peer argument ordering, task ordering, candidate ordering and confidence tie breaks are reproducibly seeded. Model/provider seed support is opt-in; it is not a guarantee of deterministic server behavior.

## Selection policy and estimands

`independent` collects all five-member panels and persists them before any debate. `screen` compares labels to the separate gold file and writes categories; it cannot change the collection policy. `deliberate` reads the frozen panels. The default selection rule is initial disagreement, which requires at least two distinct answer labels and does not use gold labels. It retains majority-correct cases, majority-wrong cases and fragmented votes.

Unanimous teams stop under this policy. Their initial decision is the final decision of every condition, so the study-level estimate is for **a policy of stopping unanimous panels and applying the condition to disagreement**. For unconditional application of every condition use `selection: all`. Do not interpret the default as evidence about debate on unanimous panels.

The focus stratum M−m+ has a wrong strict majority (at least three of five members selecting one wrong option) and at least one correct minority member. A 2–2–1 distribution has no strict majority. Classification is determined from the original shared panel for each seed/model and does not depend on treatment outcomes. Study reports show both scheduled and available focus panels; a failed initial panel has unknown category.

## Conditions and controls

Nine conditions are implemented. Majority vote uses five calls. Standard debate uses ten. Protected dissent uses ten calls if no proposal exists, fifteen if no dissent qualifies, and twenty if it triggers an extra round. Protected appeal uses ten, fifteen, or sixteen. A qualifying dissent must choose another valid option, identify a disputed claim and evidence, and meet the configured confidence threshold. Qualification is structural and self-reported, not verification of evidence quality. Highest confidence wins with seeded tie breaks; all declarations are retained. One escalation is allowed, after which strict majority or binding review resolves/abstains.

Independent revision uses ten calls and no peer arguments. It is a control for change due to additional stochastic inference without interaction. Explicit dissent uses the same common debate and a separate five-agent declaration checkpoint that explicitly lacks procedural power; declaration answers become the final panel votes. The reminder condition has a separate five-agent checkpoint with original/current answers and peer arguments but no formal dissent. Both return unresolved without extra calls if common debate has no proposal.

The extra-round and independent-review controls share a separate five-call neutral checkpoint. Its assessments are not final votes. Their escalation is yoked to the protected checkpoint: they receive additional computation exactly on the same questions as the protected branches. The extra-round control uses neutral checkpoint arguments for a final group revision; the reviewer control sees only the problem and an anonymised proposed argument and can choose any original option or unresolved. Without an escalation they retain the common debate result. This gives identical logical call counts to the paired protected conditions, not identical token costs. Actual calls, retries, tokens and charges are reported. These yoked controls are experimental controls, not standalone deployment policies.

The protected reviewer instead sees exactly two candidate arguments in seeded random order and can select one or unresolved. Neither reviewer receives support counts or member identities. Proposed arguments preferably come from initial independent responses. Protected alternatives use the disputed claim and evidence. A sentence filter removes common social words; it can remove substantive content and cannot ensure perfect semantic blinding. Audit prompts. The different sources of the two arguments and the differently constrained reviewer answer spaces are explicit design limitations; the comparisons do not isolate every possible cause of improvement.

The maximum physical logical-call count across shared prefixes and all nine branches is 47 per selected task. Standalone protocol totals must not be summed as physical expenditure. Under unanimity stopping each nonselected task uses five calls total. Retries add request attempts without changing the logical experimental condition.

## Failure policy

Transient network failures and designated transient HTTP/API errors receive at most `max_attempts` attempts per invocation batch with exponential backoff and deterministic jitter. HTTP `Retry-After` takes precedence when larger, with HTTP-date support. If a server asks for more than 60 seconds, the request is deferred with a persisted not-before time. A subsequent explicit `--retry-failed` cannot send it before that time. Authentication/ordinary insufficient-credit/invalid request errors stop collection; malformed output and refusal remain invalid rather than being resampled based on correctness.

The frozen output-length recovery policy starts at 8,192 tokens and doubles the allowance only for explicit `finish_reason: length`, up to 32,768 tokens. Retries share the normal attempt and cost limits; all attempts and their actual allowances, responses and usage are retained. Only the truncated call is repeated, without changing its prompt or inspecting correctness. The next allowance persists across resume. Report these retries and their costs. Ceiling exhaustion is still missing data. Configure allowances within the selected provider/model's supported limits before collection; older runs remain frozen under their original policy.

Every attempt is journaled before dispatch. Completed calls are reused. A pending attempt after an interrupted process may already have been charged. Resubmission requires `--retry-failed`; this preserves all earlier attempts and allows another bounded batch. No API idempotency guarantee is assumed. Missing usage remains unknown, including failed attempts that might have incurred costs. Unknown costs are not zero. The hard study budget is a request-attempt cap; the reported-dollar stop threshold is soft and checked between requests.

Nonfatal exhausted/invalid calls mark that task/stage failed and collection proceeds to other questions. Independent failures must be retried before deliberation when eligible. A branch failure can leave some earlier calls cached, but a full task result is only committed after all configured branches complete; primary comparisons therefore use complete paired outcomes and disclose unavailable pairs. This is conservative bookkeeping, not missing-at-random evidence. Report failure rates and assess differential failure as a threat to validity. Operational success-over-scheduled counts unavailable outcomes as unsuccessful, separately from conditional accuracy. Never silently delete failed tasks or repeatedly sample invalid output until a desirable result appears.

No two collection processes may write the same study directory simultaneously. Data, source code, inference settings, seeds, selection and analysis plan are hashed; changing them requires a new study directory. Operational caps and explicit retry authorization are logged per invocation and may be changed to continue a budget-paused study.

## Outcomes

Report accuracy, coverage, accuracy when resolved, focus prevalence, correct-minority recovery, wrong unanimous consensus/suppression, correct-minority survival, correct/wrong agent transitions, false dissent, false qualifying dissent, escalation and resources. Unresolved is not a correct answer or a wrong consensus. A correct independent appeal need not restore any panel member, so panel survival stays separate from final-decision recovery. Suppression requires all five final panel members and the final decision to select the same wrong answer on an initial M−m+ task.

The tables report available/scheduled denominators and unique-question counts. Absolute rates pooled across seeds are descriptive proportions of panels. Complete-case accuracy divides by available outcomes; operational success-over-scheduled divides by all scheduled outcomes. Agent transitions are descriptive counts only. Do not treat the five agents as five independent experimental units.

## Paired inference

The config enumerates treatment/baseline comparisons. For each model, these are evaluated for accuracy, focus recovery, and focus suppression, across the complete source mixture and each source separately. Family tables are descriptive. All comparisons use identical task/seed pairs available in both conditions. The effect is the mean treatment-minus-baseline binary outcome across those pairs. Positive accuracy/recovery differences favor the treatment; negative suppression differences favor it.

A stratified question-cluster percentile bootstrap resamples question IDs within source/family strata with replacement and carries every available repetition of that question together. Each replicate recalculates the panel-weighted paired difference. This preserves dependence across seeds and between conditions. It does not model uncertainty across model families or across arbitrary task generators beyond the sampled task strata. Uneven missing repetition counts affect weighting and are disclosed by missing-pair counts. Config controls resample count and seed. Fewer than two unique questions yields no interval; constant bootstrap distributions are flagged rather than treated as certainty.

If each question contributes only one paired observation, the p-value is the exact two-sided McNemar/binomial discordance test. If questions contribute multiple repetitions, use a sign flip of the entire question's summed paired differences: enumerate all sign assignments with at most twelve nonzero clusters, otherwise use a Monte Carlo sign flip with a plus-one correction. This tests under cluster-level paired exchangeability/symmetry assumptions; it is an exploratory test, not proof of a causal social mechanism. Do not run ordinary McNemar on all repeated panels as if independent.

Holm adjustment includes all nonempty predeclared endpoint/source-scope comparisons within each model. Adjustment families and sizes are written with the results. Cross-model confirmatory claims need a larger predeclared correction family. Bootstrap intervals are marginal 95% intervals, not simultaneous intervals adjusted by Holm. The notebook exposes raw and adjusted p-values and effect intervals, rather than producing significance-based conclusions.

Fifty or six hundred questions are planning quantities, not power guarantees. If the focus stratum is sparse, its effect estimates will be uncertain. Estimate its prevalence on disjoint live development data before committing to a confirmatory sample. Controlled constructed teams, if later added, must be reported separately from natural disagreement prevalence.

## Reporting and reproducibility

`research_report.ipynb` is analysis-only. It reruns validated report generation, then displays data integrity/collection status, strata, accuracy/coverage, minority outcomes, paired effects, transitions, resources and a deterministic qualitative audit sample. PNG/PDF figures, derived CSV tables, package versions and the executed notebook are exported under the run. Mock studies are conspicuously labelled synthetic in the notebook, reports and figures.

The analysis source hash is recorded separately from the collection source hash. Physical accounting includes all attempted requests in all units, even when a task failed. Standalone condition accounting charges each successful condition its shared and private calls and all attempts attached to them; the physical ledger separately captures unallocated failed work. Latency sums are serial request durations, excluding retry sleeps. Timestamps retain overall elapsed history.

The notebook implements the specified statistical plan; its presence does not establish novelty, dataset difficulty, sufficient power or publishability. The remaining live work is to validate the chosen provider and model on disjoint development problems, inspect reasoning/blinding, freeze the final configuration, and collect the study.

## References

- [OpenRouter errors and Retry-After](https://openrouter.ai/docs/api_reference/errors-and-debugging)
- [SciPy exact binomial-test documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html)
- [SciPy paired bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
- [BBH original repository](https://github.com/suzgunmirac/BIG-Bench-Hard)

The standard-library statistical implementation is validated against exact small examples; these references document the underlying procedures, not a dependency on SciPy.
