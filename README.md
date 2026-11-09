# OpenArm Dataset: technical experiments

Two independent engineering investigations of
[enactic/openarm_dataset](https://github.com/enactic/openarm_dataset), the
toolkit that validates, repairs and converts OpenArm robot recordings
into training formats (LeRobot v2.1/v3.0, GR00T, Rerun).

This repository is a copy of upstream at
[`3d291fe`](https://github.com/enactic/openarm_dataset/commit/3d291fe8a71153de03d76ca9a70c4fdb88fc1929)
(2026-11-04), with each experiment on its own branch. It is personal
research. It is **not affiliated with or endorsed by Enactic**, and
nothing here has been submitted upstream. The upstream code is
Apache-2.0 (see [LICENSE.txt](LICENSE.txt)); its original README is
[README.upstream.md](README.upstream.md).

No OpenArm hardware was used. All experiments run on the repository's
recorded test fixtures.

## 1. Export provenance: issue #71 (branch [`gh71-provenance`](../../tree/gh71-provenance))

**Question.** What metadata is lost when an OpenArm recording is
converted into LeRobot or GR00T training data, and can it be kept
without breaking the training formats?

**Findings.**
- The LeRobot v2.1, v3.0 and GR00T exports keep only the task prompt.
  Episode ids, equipment and leader firmware versions, task descriptions
  and the effect of `success_only`/`valid_only` filtering are lost. Two
  exports of the same recording, filtered differently, can have identical
  episode tables while containing different physical demonstrations.
- Measured loader behaviour decided the design: lerobot 0.7.0 silently
  drops unknown `info.json` keys and refuses undeclared data columns, but
  ignores a separate metadata file.

**Change.** A versioned `meta/openarm.json` sidecar records the source
hardware, conversion options and the source of every exported episode.
Operator and location are withheld unless opted in. 78 regression tests;
every other export file is byte-identical to upstream in all three formats.

**Read:**
[TECHNICAL_ARTICLE.md](../../blob/gh71-provenance/research/TECHNICAL_ARTICLE.md)
·
[PROVENANCE_DESIGN.md](../../blob/gh71-provenance/research/PROVENANCE_DESIGN.md)
·
[ARCHITECTURE_AUDIT.md](../../blob/gh71-provenance/research/ARCHITECTURE_AUDIT.md)
·
[ENGINEERING_REPORT.md](../../blob/gh71-provenance/research/ENGINEERING_REPORT.md)
·
[REVIEWER_GUIDE.md](../../blob/gh71-provenance/research/REVIEWER_GUIDE.md)

## 2. A crash after the work is done: issue #45 (branch [`gh45-exit-abort`](../../tree/gh45-exit-abort))

**Question.** Why does `openarm-dataset-repair` occasionally exit with
SIGABRT ("terminate called without an active exception") in CI, after
printing that the repair succeeded?

**Findings** (Linux, Python 3.12, pyarrow 26.0.1, 2000 runs per case):

| case | aborts |
|---|---|
| repair CLI, September workaround reverted (one line) | 79 |
| repair CLI on upstream `main` | 0 |
| read a dataset through `Dataset`, then exit: upstream | 20 |
| same, with the fix | 0 |
| convert CLIs, upstream or fixed | 0 |
| pyarrow reading via a Python file object / by path | 139 / 0 |

- Cause: [apache/arrow#34314](https://github.com/apache/arrow/issues/34314).
  An Arrow thread releases a Python-backed buffer during interpreter
  shutdown; glibc's forced unwind reaches a `noexcept` C++ destructor and
  `std::terminate` aborts the process.
- The flaky test is already fixed on upstream `main` by an unverified
  workaround. The same unsafe read remains in `Dataset`. It aborts for
  code that reads and then exits, but was not observed in the shipped CLIs.
- Preliminary: on Python 3.13 and 3.14 one run each hung instead of
  aborting.

**Change.** A helper that reads parquet by path, used at every read site,
and deterministic tests that no read goes through a Python file object.

**Read:**
[TECHNICAL_ARTICLE.md](../../blob/gh45-exit-abort/research/gh45/TECHNICAL_ARTICLE.md)
·
[evidence/](../../tree/gh45-exit-abort/research/gh45/evidence)
·
[stress harness](../../blob/gh45-exit-abort/research/scripts/exit_abort_stress.py)

## Reproducing

```bash
git checkout gh71-provenance     # or gh45-exit-abort
uv sync -p 3.12 --extra lerobot-dataset-v2.1   # or lerobot-dataset-v3.0 (Linux)
uv run pytest -rs
```

Each branch's `research/` directory lists the exact commands and
environments behind every number.
