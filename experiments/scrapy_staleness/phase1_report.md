# Phase 1: ground truth and staleness detection (no LLM)

Run 2026-10-10T23:52:44Z · ArchAI 0.2.1-pilot (engine `ebfae8c4cd45c341`, commit `ec911638feb7`) · Python 3.13.9 · LLM used: no.

Reproduce: `python experiments/scrapy_staleness/phase1.py` (see README.md).

## 1. Graphs per tag

Only the `scrapy/` package of each tag is analyzed (`git archive <tag> scrapy`). Edges are unique (source, target) pairs of `scrapy.*` modules linked by a **module-scope** import; the stored graphs also keep function-level, type-checking and dynamic imports.

| Tag | Commit | Modules | Module-scope edges | Import records (all scopes) | Parse failures | Build (s) |
|---|---|---|---|---|---|---|
| 2.10.0 | `88327c7c58` | 170 | 530 | 555 | 0 | 0.64 |
| 2.11.0 | `f2fb4760d2` | 171 | 534 | 565 | 0 | 0.65 |
| 2.12.0 | `b1f9e56693` | 170 | 510 | 733 | 0 | 1.56 |
| 2.13.0 | `82a3245158` | 172 | 514 | 756 | 0 | 0.66 |
| 2.14.0 | `3ac1192f35` | 174 | 577 | 812 | 0 | 0.64 |
| 2.15.0 | `47e25fbbb5` | 178 | 610 | 852 | 0 | 0.71 |
| 2.16.0 | `abe9c63841` | 174 | 594 | 828 | 0 | 0.61 |
| 2.17.0 | `feb692f552` | 174 | 603 | 839 | 0 | 0.64 |
| 2.18.0 | `2216063c06` | 176 | 617 | 860 | 0 | 0.82 |
| 2.19.0 | `8026deeaac` | 179 | 635 | 883 | 0 | 0.70 |

**Reproduction check** (2.10.0 → 2.19.0): 170 → 179 modules, 530 → 635 edges; modules added 24, removed 15 (of which 3 detected as moves); edges added 236, removed 131. These match the numbers given in the study prompt.

## 2. Drift relative to 2.10.0

| Checked at | Releases | Commits | Days | Modules + | Modules − | Moved | Edges + | Edges − | Edges kept |
|---|---|---|---|---|---|---|---|---|---|
| 2.11.0 | 1 | 124 | 44 | 1 | 0 | 0 | 6 | 2 | 528 |
| 2.12.0 | 2 | 624 | 471 | 4 | 4 | 0 | 56 | 76 | 454 |
| 2.13.0 | 3 | 789 | 642 | 6 | 4 | 0 | 80 | 96 | 434 |
| 2.14.0 | 4 | 974 | 884 | 8 | 4 | 1 | 154 | 107 | 423 |
| 2.15.0 | 5 | 1068 | 978 | 12 | 4 | 1 | 192 | 112 | 418 |
| 2.16.0 | 6 | 1121 | 1018 | 14 | 10 | 1 | 189 | 125 | 405 |
| 2.17.0 | 7 | 1202 | 1067 | 15 | 11 | 0 | 198 | 125 | 405 |
| 2.18.0 | 8 | 1392 | 1112 | 18 | 12 | 3 | 218 | 131 | 399 |
| 2.19.0 | 9 | 1460 | 1132 | 21 | 12 | 3 | 236 | 131 | 399 |

Moves detected by git between 2.10.0 and 2.19.0: `scrapy.core.http2` → `scrapy.core._http2` (100%), `scrapy.core.http2.protocol` → `scrapy.core._http2.protocol` (75%), `scrapy.core.http2.stream` → `scrapy.core._http2.stream` (70%).

The full matrix for all 55 ordered pairs is in `results/phase1/drift_matrix.json`.

## 3. Staleness verifier vs ground truth

`ai_architect/standards/staleness.py` labels every fact of an old graph against a newer checkout (window: cited line ±5). Ground truth: an edge fact is stale if its (source, target) pair is no longer a module-scope edge at the checked tag; a module fact is stale if the module name no longer exists (moves count as stale).

### Edge facts (2.10.0 graph)

| Checked at | Facts | Truly stale | Labelled STALE | STALE precision | STALE recall | Unchanged → VERIFIED | False VERIFIED | UNVERIFIABLE |
|---|---|---|---|---|---|---|---|---|
| 2.11.0 | 530 | 2 | 25 | 8.0% | 100.0% | 95.6% | 0 | 0 |
| 2.12.0 | 530 | 76 | 224 | 33.9% | 100.0% | 67.4% | 0 | 0 |
| 2.13.0 | 530 | 96 | 241 | 39.8% | 100.0% | 66.6% | 0 | 0 |
| 2.14.0 | 530 | 107 | 277 | 38.6% | 100.0% | 59.8% | 0 | 0 |
| 2.15.0 | 530 | 112 | 293 | 38.2% | 100.0% | 56.7% | 0 | 0 |
| 2.16.0 | 530 | 125 | 294 | 42.5% | 100.0% | 58.3% | 0 | 0 |
| 2.17.0 | 530 | 125 | 298 | 41.9% | 100.0% | 57.3% | 0 | 0 |
| 2.18.0 | 530 | 131 | 321 | 40.8% | 100.0% | 52.4% | 0 | 0 |
| 2.19.0 | 530 | 131 | 330 | 39.7% | 100.0% | 50.1% | 0 | 0 |

### Module facts (2.10.0 graph)

| Checked at | Facts | Truly stale | STALE precision | STALE recall | Unchanged → VERIFIED | False VERIFIED |
|---|---|---|---|---|---|---|
| 2.11.0 | 170 | 0 | n/a | n/a | 100.0% | 0 |
| 2.12.0 | 170 | 4 | 100.0% | 100.0% | 100.0% | 0 |
| 2.13.0 | 170 | 4 | 100.0% | 100.0% | 100.0% | 0 |
| 2.14.0 | 170 | 5 | 100.0% | 100.0% | 100.0% | 0 |
| 2.15.0 | 170 | 5 | 100.0% | 100.0% | 100.0% | 0 |
| 2.16.0 | 170 | 11 | 100.0% | 100.0% | 100.0% | 0 |
| 2.17.0 | 170 | 11 | 100.0% | 100.0% | 100.0% | 0 |
| 2.18.0 | 170 | 15 | 100.0% | 100.0% | 100.0% | 0 |
| 2.19.0 | 170 | 15 | 100.0% | 100.0% | 100.0% | 0 |

**Why unchanged edges were labelled STALE** (false positives, summed over the 9 targets): import statement no longer present: 720; statement no longer within 5 lines: 678.

In every one of these cases the dependency still exists but the receipt no longer matches: the cited statement's text changed, or it moved further than the window. How the 'no longer present' statements changed:

| Checked at | Names added | Names removed | Names replaced | Rewritten in another form |
|---|---|---|---|---|
| 2.11.0 | 5 | 0 | 0 | 0 |
| 2.12.0 | 49 | 7 | 12 | 0 |
| 2.13.0 | 48 | 6 | 15 | 0 |
| 2.14.0 | 51 | 9 | 25 | 0 |
| 2.15.0 | 56 | 9 | 32 | 0 |
| 2.16.0 | 52 | 11 | 33 | 0 |
| 2.17.0 | 52 | 11 | 32 | 0 |
| 2.18.0 | 56 | 11 | 34 | 0 |
| 2.19.0 | 57 | 12 | 35 | 0 |

**All 45 pairs (every older graph against every newer tag):** false VERIFIED labels in total: 0. Edge STALE precision ranges 8.0%–65.3%, recall 100.0%–100.0%. Per-pair numbers: `results/phase1/verifier_evaluation.json`.

![Verifier accuracy vs distance](plots/verifier_accuracy_vs_distance.svg)

### Window sensitivity (secondary analysis)

The 5-line window was fixed before the run. Other windows, 2.10.0 graph, edge facts:

| Checked at | w=0: precision / recall / unchanged→VERIFIED | w=5: precision / recall / unchanged→VERIFIED | w=20: precision / recall / unchanged→VERIFIED | w=whole-file: precision / recall / unchanged→VERIFIED |
|---|---|---|---|---|
| 2.11.0 | 2.0% / 100.0% / 81.8% | 8.0% / 100.0% / 95.6% | 28.6% / 100.0% / 99.1% | 28.6% / 100.0% / 99.1% |
| 2.12.0 | 15.2% / 100.0% / 6.8% | 33.9% / 100.0% / 67.4% | 52.4% / 100.0% / 84.8% | 52.8% / 100.0% / 85.0% |
| 2.13.0 | 19.3% / 100.0% / 7.4% | 39.8% / 100.0% / 66.6% | 56.8% / 100.0% / 83.2% | 58.2% / 100.0% / 84.1% |
| 2.14.0 | 21.4% / 100.0% / 6.9% | 38.6% / 100.0% / 59.8% | 54.3% / 100.0% / 78.7% | 55.4% / 100.0% / 79.7% |
| 2.15.0 | 22.2% / 100.0% / 6.2% | 38.2% / 100.0% / 56.7% | 52.1% / 100.0% / 75.4% | 53.3% / 100.0% / 76.6% |
| 2.16.0 | 24.5% / 100.0% / 4.9% | 42.5% / 100.0% / 58.3% | 55.1% / 100.0% / 74.8% | 56.3% / 100.0% / 76.0% |
| 2.17.0 | 24.6% / 100.0% / 5.4% | 41.9% / 100.0% / 57.3% | 55.3% / 100.0% / 75.1% | 56.6% / 100.0% / 76.3% |
| 2.18.0 | 25.7% / 100.0% / 5.0% | 40.8% / 100.0% / 52.4% | 55.0% / 100.0% / 73.2% | 56.2% / 100.0% / 74.4% |
| 2.19.0 | 25.6% / 100.0% / 4.8% | 39.7% / 100.0% / 50.1% | 54.1% / 100.0% / 72.2% | 55.3% / 100.0% / 73.4% |

## 4. Verify vs rebuild time

Median of 3 runs, 2.10.0 graph checked against each tag (verification reads only the files the old facts cite; rebuild parses the whole package).

| Checked at | Verify (s) | Rebuild (s) | Verify / rebuild |
|---|---|---|---|
| 2.11.0 | 0.240 | 0.500 | 0.48 |
| 2.12.0 | 0.275 | 0.527 | 0.52 |
| 2.13.0 | 0.287 | 0.527 | 0.55 |
| 2.14.0 | 0.337 | 0.580 | 0.58 |
| 2.15.0 | 0.302 | 0.619 | 0.49 |
| 2.16.0 | 0.305 | 0.617 | 0.50 |
| 2.17.0 | 0.299 | 0.634 | 0.47 |
| 2.18.0 | 0.295 | 0.659 | 0.45 |
| 2.19.0 | 0.297 | 0.676 | 0.44 |

## 5. Missing knowledge (not a staleness error)

Facts that exist at the later tag but not in the 2.10.0 graph. The verifier cannot see these, by design: it can only re-check what the old graph claims.

| Checked at | New modules | New edges | New edges as share of current edges |
|---|---|---|---|
| 2.11.0 | 1 | 6 | 1.1% |
| 2.12.0 | 4 | 56 | 11.0% |
| 2.13.0 | 6 | 80 | 15.6% |
| 2.14.0 | 9 | 154 | 26.7% |
| 2.15.0 | 13 | 192 | 31.5% |
| 2.16.0 | 15 | 189 | 31.8% |
| 2.17.0 | 15 | 198 | 32.8% |
| 2.18.0 | 21 | 218 | 35.3% |
| 2.19.0 | 24 | 236 | 37.2% |

![Staleness vs distance](plots/staleness_vs_distance.svg)

## 6. Threats to validity

- One project, Python only, import-level structure only.
- Ground truth and verifier share ArchAI's extraction and resolution code (`resolve_import_targets`). Agreement therefore shows the verifier is consistent with the graph builder, not that the builder is correct. A bug in shared resolution would affect both.
- An edge fact counts as unchanged when its (source, target) pair survives, even if the import statement was rewritten. Such rewrites are counted as verifier false positives above.
- Moves are detected by git rename heuristics (50% similarity) and are reported, but scored as stale.
- Timings are wall-clock on one machine and include Python start-up effects inside the process; they are comparable to each other, not absolute.
- The Python grammar used to parse is the running interpreter's (see run metadata).
