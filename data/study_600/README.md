# Fresh evaluation dataset — 300 questions

Prepared for the fresh half of the 600-question hybrid study. `fresh/tasks.jsonl` contains 100 ordering, 100 Boolean, and 100 shortest-path problems; `fresh/answers.jsonl` contains separate reference labels and verifier inputs. Each answer is checked by two exact algorithms. The generator uses a newly chosen random seed, recorded in `manifest.json` and `fresh/manifest.json` along with content hashes.

These are actual generated problems, not mock model responses. The mock backend used during software validation is a separate test fixture.

The sample is frozen across protocols and repetitions. Difficulty has not yet been calibrated on a live model. Use disjoint development problems for prompt/model calibration; if generator changes are needed, prepare a new evaluation directory before data collection. Reproducibility does not require publishing evaluation questions before collection.

From the repository root, reproduce this exact generated set into a new directory by supplying the recorded `fresh_seed` to `python -m dissent generate --count 300 --seed YOUR_RECORDED_SEED --out data/fresh_reproduced`.

The public BBH portion remains in `data/bbh_300`. `configs/study.json` references both sources, keeping their identities separate in all reporting. No live results are included here.
