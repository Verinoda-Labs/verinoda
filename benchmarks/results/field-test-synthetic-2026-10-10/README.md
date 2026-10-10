# Synthetic field-test corpus: answer paths and relation rules (2026-10-10)

Two measurements on a synthetic Turkish biology corpus at the biology field test's scale (round 6,
`docs/SYMBIOSIS-GAPS.md`: 31-41 topics), made because the field test's own corpus and gold data are not in this
repository.

1. **Answer paths for a product** (the 20.8 decision, D183): what it costs and what it finds when a product answers on
   the standard library only, with Verinoda's `query --sentences` (D180), or with the plain `query`.
2. **Relation rules** (D181): the edges `verinoda relations` reads against the ones the generator planted.

**Read every number below with this in mind:** the corpus is synthetic and templated, and the generator, the questions,
the planted answers and the rules were all written by the same person who measured them. It is not independent, and it is
not the field test. The relation result in particular is self-consistency: the generator's five sentence templates are
among the patterns the relation rules were written for.

## Files

| File | What |
|---|---|
| `gen.py` | The corpus: 40 topics with a prerequisite map, 4 filler sentences and one co-mention ("… sınavlarda birlikte sorulabilir") per topic, and one planted sentence per prerequisite in one of five templates (three in the later topic's file, two in the earlier one's). `gen.py DIR 10` makes 400 files: the topics again with a qualifier word ("Doku ormanda"). Seed 7. Also writes the questions and their planted sentences (`gold.json`). |
| `stdlib_answer.py` | A stand-in for a product on the standard library only (Symbiosis's own `query.py` is not in this repository): every Markdown file, sentences, ranked by shared words (five-letter stems), the ten best. |
| `vq.py` | One cold product call that depends on Verinoda: import, load the index, answer, peak memory. |
| `measure.py` | Measurement 1. Writes `results.json` into the corpus folder. |
| `answers-40-files.json`, `answers-400-files.json` | Measurement 1's `results.json`; only the `corpus` field was changed, from the absolute path of a temporary folder to the corpus folder name. |
| `eval_rel.py` | Measurement 2: prints the read edges against `topics.json`'s `prerequisites`. |
| `relations-40-files.json`, `relations-400-files.json` | Measurement 2's output. |

Reproduce from this folder, with a Python that imports Verinoda:

```
python gen.py c40 1 && python gen.py c400 10
python measure.py c40 && python measure.py c400        # c40/results.json, c400/results.json
python eval_rel.py c40 && python eval_rel.py c400
```

Measured on Windows 11, Python 3.12; measurement 1 with the code of commit `a824dd8`, measurement 2 with the code of
commit `95c43fe` (the relation rules as in `250b46f`).

## 1. Answer paths (35 questions on 40 files, 30 on 400)

Cold: a new process per question. Warm: one process, the index loaded once. Tokens: characters / 4, an estimate.
Recall: the share of a question's planted sentences the answer's text contains.

| | 40 files: stdlib / sentences / passages | 400 files: stdlib / sentences / passages |
|---|---|---|
| Cold, median s | 0.077 / 0.448 / 0.47 | 0.22 / 0.446 / 0.465 |
| Warm, median ms | 0.81 / 13.16 / 24.67 | 8.4 / 20.02 / 29.3 |
| Answer, median tokens (est.) | 218 / 277 / 334 | 276 / 322 / 315 |
| Evidence recall | 0.457 / 0.571 / 0.70 | 0.283 / 0.35 / 0.167 |
| Answers with all evidence | 15 / 19 / 22 of 35 | 7 / 9 / 5 of 30 |
| MRR of the first evidence line | 0.349 / 0.44 / - | 0.063 / 0.265 / - |
| First evidence in the top 3 | 13 / 16 / - of 35 | 1 / 7 / - of 30 |
| Lines that are evidence | 0.06 / 0.077 / - | 0.033 / 0.047 / - |
| Peak memory, MB | 15.1 / 38.3 / 38.5 | 16.9 / 41.0 / 41.5 |

Index: first build 1.34 s / 6.34 s; `update` with nothing changed 0.46 s / 0.52 s, after one file edited 0.95 s / 4.74 s;
0.59 MB / 2.49 MB against a corpus of 0.017 MB / 0.188 MB. Start-up of a new process: Python 0.047 s, the standard
library imports 0.056 s, Verinoda's query path 0.32 s (0.45 s in a clean virtual environment with no extras; about 0.2 s
of it is `networkx`). A plain `pip install` of Verinoda: 63 packages, 293 MB of site-packages (`scipy` 87 MB).
Verinoda calls no language model on this path: a token cost exists only when a model reads the answer.

## 2. Relation rules

| | 40 files | 400 files |
|---|---|---|
| Planted edges / read / correct | 46 / 46 / 46 | 460 / 460 / 460 |
| Reversed, wrong | 0, 0 | 0, 0 |
| Co-mentions not read as relations | 40 | 400 |
| Seconds (one process) | 0.42 | 2.08 |

The seconds vary with the machine's load: earlier runs of the same rules took 0.23-0.29 s and 0.36-0.46 s.

By rule (40 files): `tr-anlamak-icin` 15, `tr-ablative-once` 11, `tr-uzerine-kurulur` 11, `tr-ablative-sonra` 6,
`tr-onkosul` 3 (the per-rule counts of both sizes are in the files).

**Not measured:** the field test's corpus and gold (the branch `biyo-platform-test` is not on the remote), free prose,
the real Symbiosis product, and whether a model or a person answers better with any of these paths.
