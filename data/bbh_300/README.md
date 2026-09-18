# BBH public benchmark subset — 300 questions

This is the public half of the proposed 600-question hybrid study. It contains genuine public benchmark questions, not model-generated questions or synthetic mock responses. It does not contain experimental model responses.

| BBH task | Selected | Available in pinned source |
|---|---:|---:|
| logical_deduction_five_objects | 100 | 250 |
| logical_deduction_seven_objects | 100 | 250 |
| tracking_shuffled_objects_seven_objects | 100 | 250 |

Source: [official BIG-Bench Hard repository](https://github.com/suzgunmirac/BIG-Bench-Hard), pinned at [9ee07bd481feebf959a6b59d61ea57bdcf30964d](https://github.com/suzgunmirac/BIG-Bench-Hard/tree/9ee07bd481feebf959a6b59d61ea57bdcf30964d). Exact download timestamps, URLs, source byte checksums, selected indices and prepared-data hashes are in `manifest.json` and `raw/sources.json`.

## Files

- `tasks.jsonl`: 300 questions with original option wording and order. Agent-safe schema; no answer keys or worked solutions.
- `answers.jsonl`: original correct option labels, normalised from `(A)` to `A`, for automated scoring only.
- `provenance.jsonl`: each question's original file, zero-based example index, and example checksum.
- `manifest.json`: source version and complete sampling specification.
- `raw/`: unchanged official JSON files (750 examples), license, and documentation, retained for reproducibility. Do not feed this directory to agents: it includes answers.

Sampling uses seed 2027. Within each family, rank source indices by SHA256 of canonical JSON `[seed, family, index]`, take the first 100, and write them in source order. This selection never looks at model responses or correctness. All 750 source rows were checked for valid options, target labels and lossless question reconstruction. This validates conversion, not the logical correctness of every original benchmark annotation.

The original BBH license is retained in `raw/LICENSE`. Retain the benchmark's canary/no-training notice and cite both the BBH and BIG-Bench papers using the citations in `raw/README.md`. This public benchmark may have appeared in model training; no unseen-data claim is made.

## Reproduce or run

From the repository root, reproduce without internet into a new directory:

```powershell
python -m dissent.bbh --raw data/bbh_300/raw --out data/bbh_reproduced --per-family 100 --seed 2027
```

To download the pinned source again, omit `--raw` and choose a new output directory. Existing prepared datasets are not overwritten.

The dataset works with the existing four-protocol runner:

```powershell
python -m dissent run --tasks data/bbh_300/tasks.jsonl --out runs/bbh-offline --backend mock --max-calls 6300
python -m dissent analyze --tasks data/bbh_300/tasks.jsonl --answers data/bbh_300/answers.jsonl --run runs/bbh-offline
```

Mock outputs test software only. For a real experiment use the OpenRouter settings in the root README and a new run directory. No paid experiment was launched while acquiring this dataset.

Scoring automatically creates `summary.json`, `report.md` and `classifications.jsonl`. The classification file records each question's five initial answers, vote counts, correct-agent indices and initial team category. No human review of all responses is required. An example with reference label A and responses A/B/B/B/B is automatically classified as majority-wrong/minority-correct. Invalid response formats fail validation and need inspection; reasoning quality and ambiguous benchmark items merit a manual audit sample.

There are **1,500 initial responses** for these 300 public questions at five agents each. The proposed additional 300 fresh questions bring the independent-response count to **3,000**. The legacy `run` command runs four protocols sequentially per question. The new `python -m dissent.study independent`, `screen`, and `deliberate` commands implement independent-first screening and the nine-condition research suite; see the root README. Up to 6,300 physical calls are possible for all four protocols on this public subset, hence the larger cap in the example.

Treat this frozen sample as the planned evaluation set. Develop prompts and calibrate difficulty on disjoint questions; do not tune against its observed treatment outcomes. The fresh 300-question half should be generated and frozen separately after development. Report public and generated results separately as well as in aggregate.
