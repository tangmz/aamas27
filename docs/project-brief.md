## Project Goal

We are developing an AAMAS 2027 research project tentatively titled:

**The Right to Dissent: Preventing Premature Consensus in LLM Multi-Agent Teams**

The central objective is to study whether multi-agent systems can become less reliable when agents converge too quickly on a majority opinion, especially when one or more minority agents initially hold the correct answer.

The project focuses on the idea that multi-agent systems should not only optimise **how agents reach consensus**, but also define **when consensus is allowed to close**.

## Core Research Problem

In an LLM multi-agent team, agents may independently produce different answers. During discussion, a correct minority agent may abandon its answer after seeing several incorrect agents agree with one another.

This can create **premature false consensus**:

1. at least one agent initially has the correct answer;
2. the majority is initially wrong;
3. discussion causes the correct minority position to disappear or lose influence;
4. the final team answer is incorrect.

The project aims to determine whether a formal **protected dissent mechanism** can reduce this failure.

## Main Research Question

**Can a protected right-to-dissent protocol reduce premature false consensus in LLM multi-agent teams without imposing excessive computational or deliberation cost?**

## Main Hypothesis

Standard multi-agent debate can sometimes produce socially induced degradation, where:

**Correct → Incorrect**

after agents observe the majority opinion.

A protected dissent protocol should reduce these harmful transitions and increase the probability that a correct minority position is reconsidered before the team finalises its answer.

## Proposed Contribution

Instead of treating disagreement merely as another message in a debate, the project treats dissent as a **procedural capability**.

An agent can formally invoke:

**DISSENT**

and provide:

- its alternative answer;
- the specific claim or reasoning step it disputes;
- justification or evidence;
- confidence.

A qualifying dissent can prevent immediate finalisation and trigger an institutional response such as:

- another structured deliberation round;
- independent review;
- an appeal mechanism;
- or an unresolved/abstain outcome.

The novelty is therefore not simply “minority agents can sometimes be correct.”

The contribution is to study **institutional mechanisms that protect useful disagreement before collective closure**.

## Main Experimental Conditions

The planned experiment compares several coordination protocols.

### 1. Independent Majority Vote

Five agents solve the same problem independently.

No communication occurs.

The majority answer becomes the final answer.

### 2. Standard Multi-Agent Debate

Agents first answer independently.

They then see anonymised arguments from the other agents, revise their positions, and vote again.

The final answer is chosen by majority.

### 3. Explicit Dissent

Agents debate as above, but before finalisation each agent must explicitly choose:

**AGREE** or **DISSENT**.

A dissenting agent must explain what it disputes.

However, dissent itself does not yet have procedural power.

### 4. Protected Dissent

A qualifying dissent prevents the team from immediately finalising its answer.

The system must conduct additional reconsideration.

### 5. Protected Dissent + Independent Appeal

A dissent can trigger a new reviewing agent that has not participated in the original discussion.

The reviewer sees:

- the original problem;
- the majority argument;
- the dissenting argument.

The reviewer should not be told how many agents supported each side, to reduce majority/social bias.

The reviewer can support:

- the majority;
- the dissent;
- or an unresolved outcome.

## Agent Setup

The default team size is:

**5 agents**

because this produces clear majority structures such as:

- 4 vs 1;
- 3 vs 2.

Experiments may compare:

### Homogeneous teams

All agents use the same model with independent sampling.

### Heterogeneous teams

Agents use different models or model families.

Frontier models are not required.

OpenRouter can be used as the API interface, but exact model identifiers and inference settings should be pinned and recorded for reproducibility.

## Dataset Strategy

The preferred design is hybrid.

### Public benchmarks

Use established reasoning datasets with objective ground truth.

Possible task families include:

- logical reasoning;
- mathematical reasoning;
- constraint satisfaction;
- structured reasoning.

These improve reproducibility.

### Fresh procedurally generated tasks

Generate new reasoning instances algorithmically, for example:

- ordering constraints;
- graph problems;
- scheduling problems;
- Boolean logic;
- Knights-and-Knaves-style tasks;
- arithmetic or symbolic problems.

Solutions should be automatically verified.

This reduces concerns about public benchmark contamination.

Public benchmarks are acceptable, but the paper should not claim that they are guaranteed unseen by the models.

Agents should not have web browsing or retrieval access during evaluation.

## Experimental Pipeline

### Phase 1: Independent Judgement

For every question, each agent independently returns:

- answer;
- reasoning;
- confidence;
- token usage;
- latency.

No agent sees another response.

### Phase 2: Classify Team State

Each question is categorised according to the initial answers.

Important categories include:

**Unanimous**  
All agents agree.

**Majority correct / minority wrong**

**Majority wrong / minority correct**

This last category is the main focus.

It can be written as:

**M−m+**

where the majority is wrong but at least one minority agent is correct.

### Phase 3: Natural Disagreement Experiment

Use naturally occurring M−m+ cases and compare how the different coordination protocols handle them.

The key question is whether standard debate suppresses correct minority positions and whether protected dissent preserves or recovers them.

### Phase 4: Controlled Majority-Pressure Experiment

If naturally occurring M−m+ cases are too rare, construct controlled teams using real responses previously produced by agents.

Possible configurations include:

- 2 wrong vs 1 correct;
- 3 wrong vs 1 correct;
- 4 wrong vs 1 correct.

The incorrect arguments should preferably come from genuine model outputs rather than deliberately fabricated bad answers.

This allows measurement of how increasing majority pressure affects a correct minority agent.

## Primary Metrics

### Final Team Accuracy

Proportion of tasks where the final collective answer is correct.

### Correct-Minority Recovery Rate

Among cases where the initial majority is wrong and a minority is correct:

**How often does the team eventually recover the correct answer?**

### Correct-Minority Suppression Rate

Among initially correct minority cases:

**How often does the team end with an incorrect consensus?**

This is one of the most important metrics.

### Dissent Survival Rate

Measures whether initially correct minority positions survive deliberation.

### Agent State Transitions

Track:

- Correct → Correct
- Correct → Wrong
- Wrong → Correct
- Wrong → Wrong

The particularly important failure is:

**Correct → Wrong**

because this represents socially induced degradation.

### False Dissent Rate

Measure how often dissent is triggered by an incorrect minority.

This is important because a system that encourages unlimited disagreement may become inefficient or disruptive.

### Escalation Rate

Measure how often protected dissent triggers additional review.

### Computational Cost

Measure:

- number of model calls;
- input/output tokens;
- total tokens;
- latency;
- API cost;
- number of deliberation rounds.

The paper should analyse the trade-off between reliability and computational cost.

## Dissent Ablation Study

Possible dissent variants include:

### Label-only dissent

The agent only states:

**DISSENT**

### Reasoned dissent

The agent must explain why it disagrees.

### Targeted dissent

The agent must identify the exact claim or reasoning step it disputes.

### Evidence-backed dissent

The agent must provide:

- disputed claim;
- alternative;
- justification/evidence;
- confidence.

This allows us to test whether simply giving agents permission to disagree is enough, or whether structured dissent is necessary.

## Important Experimental Controls

- Anonymise agent identities during debate.
- Randomise the order in which peer responses are shown.
- Keep prompts identical across experimental conditions except for the protocol-specific instructions.
- Use the same task instances across protocols.
- Prevent web search or retrieval during benchmark evaluation.
- Do not reveal majority vote counts to the independent reviewer.
- Record exact model IDs, temperature, top-p, max tokens, prompts, provider, access date, and seed where supported.

## Main Expected Contribution

The project aims to make five contributions:

1. **Identify and quantify premature consensus** in LLM multi-agent teams.
2. **Measure correct-minority suppression**, where interaction makes a previously correct team member wrong.
3. **Introduce a Protected Dissent Protocol** that gives disagreement procedural consequences.
4. **Evaluate whether protected dissent improves collective reliability** across public and freshly generated reasoning tasks.
5. **Measure the reliability-versus-cost trade-off** introduced by additional deliberation and review.

## Core Paper Thesis

The central thesis is:

**Multi-agent systems should not only optimise how agents reach consensus; they should also govern when consensus is allowed to close.**

## Immediate Next Step

The first implementation should be a small pilot:

- approximately 50 reasoning problems;
- 5 agents;
- 1 model;
- 4 protocols:
  - majority vote;
  - standard debate;
  - protected dissent;
  - protected dissent + independent review.

The pilot should first establish whether the phenomenon:

**correct minority → wrong consensus**

occurs often enough to study.

If it does, the experiment can then be expanded to:

- multiple models;
- public and procedurally generated datasets;
- homogeneous and heterogeneous teams;
- larger sample sizes;
- dissent ablations;
- controlled majority-pressure experiments.