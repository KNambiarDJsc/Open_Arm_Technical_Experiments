# Patch Hiring proposal: traceable OpenArm training exports (openarm_dataset#71)

Project: https://github.com/enactic/openarm_dataset
Issue: https://github.com/enactic/openarm_dataset/issues/71
Status: draft for the applicant to send. Not submitted, not accepted.

## Already done independently (not part of the proposed week)

Before writing this proposal I implemented and verified a first version on
a private branch (`research/openarm-dataset-provenance`, base `3d291fe`).
Every LeRobot v2.1, v3.0 and GR00T export writes a versioned
`meta/openarm.json` with the source equipment, frequencies, tasks,
conversion options and the source of every exported episode. Operator and
location are withheld unless requested. 78 regression tests; every
existing export file is byte-identical to upstream (data parquet, videos,
metadata); LeRobot 0.3.3 and 0.7.0 load the exports. It was built without
any input from the maintainers, so its choices are open to change. I can
share the branch and the evidence on request.

A Patch Hiring proposal for the same issue by another applicant
(H3Xobit, 2026-10-09) is already on the issue and also proposes
`meta/openarm.json`. If that proposal is accepted, the week below is
designed not to duplicate it: items 2-4 are independent of who writes the
sidecar.

## Task purpose

Make every OpenArm training export traceable to the recordings and
hardware it came from, in a form the maintainers agree on, and remove the
two places where that traceability is still lost: dataset merging and a
`valid_only` crash in the v2.1/GR00T path.

## Work contents

1. **Settle the export contract with the maintainers and land it.**
   Questions: default for operator/location (the uploader already
   publishes them on the dataset card); file name; whether the source
   episode id should also appear in LeRobot's own episode table, which
   both LeRobot versions tolerate. Adapt the branch and open a PR in the
   project's style.
2. **Fix the `valid_only` crash in the v2.1/GR00T writer.**
   `_write_metadata` reads camera shapes from `meta.episodes[0]` even when
   that episode was filtered out (`lerobot_v21.py:683`), so an export that
   excludes a first episode with a missing camera raises `IndexError` after
   writing data and videos. Reproduced on Windows and Linux. The v3.0
   writer already uses the first exported episode.
3. **Keep provenance through `openarm-dataset-merge`.** Merging renumbers
   episode ids to `0..n-1` and records nothing about which input dataset
   each episode came from, so an export of a merged dataset can only be
   traced back to the merge. Propose, agree on and implement a per-episode
   origin record (input dataset identity plus original id) in the merged
   `metadata.yaml`, and carry it into the export sidecar.
4. **Validation.** Regression tests on the repository fixtures for each
   item; byte-level comparison of export outputs against `main`; LeRobot
   loader checks in both CI extras; and, if the team can share a small
   real multi-session recording, an end-to-end run on it.

## Estimated period

One week (five working days) after acceptance.

| day | work |
|---|---|
| 1 | Contract questions answered; branch adapted; PR for item 1 opened |
| 2 | Item 2 with a regression test; review follow-ups on item 1 |
| 3 | Item 3 design note agreed (format change to merged metadata) |
| 4 | Item 3 implemented and tested, including export of a merged dataset |
| 5 | Item 4 validation, review follow-ups, Patch Hiring report |

If item 3's format change needs more discussion than a day allows, it
becomes a design note plus prototype, and days 4-5 go to review and
validation of items 1-2.

## Ambitious longer-term objective

Mixed-hardware OpenArm corpora that stay traceable from training run back
to recording session. Within one export the hardware is constant (merge
requires identical equipment), so hardware varies only between exports.
With every export carrying its identity, a training pipeline can build
mixtures by arm or leader version, hold out a hardware revision for
evaluation, and attribute regressions to specific recording setups. The
sidecar is the precondition for that; this week makes it reliable.

## Why it matters for project growth

OpenArm data is collected on more than one arm and leader version and
converted for LeRobot and GR00T. Once a corpus spans several labs and
hardware revisions, "which recordings trained this policy?" has to have an
answer from the dataset itself. The project already treats equipment as
identity (merge refuses mismatched equipment); the exports should too.

## Expected technical challenges

- LeRobot v2.1 and v3.0 store metadata differently, and lerobot 0.7.0
  drops unknown `info.json` keys and rejects undeclared data columns
  (measured). Any change must keep both loaders working.
- Merging changes the OpenArm format, so it must stay backward compatible
  with existing merged datasets and the validator.
- Privacy: operator and location must not leak by accident, and nested
  equipment fields can contain internal identifiers.
- The v3.0 writer cannot run on Windows, so CI on Linux is the reference.

## Relevant qualifications

- Python and Rust systems engineering; evaluation infrastructure,
  reliability, observability and fault testing.
- Data provenance and auditability work, including OpenMHS, an
  independent agent-to-physical-hardware execution project.
- The independent work above: audit of the conversion path, measured
  loader behaviour, a regression suite written before the fix, and a
  byte-level compatibility check against `main`.

## Exact one-week deliverables

1. A PR implementing the agreed export contract, with tests and README.
2. A PR fixing the `valid_only` first-episode crash, with a regression
   test.
3. A design note and (if agreed) a PR keeping episode origin through
   merge and into the export sidecar.
4. A short validation report: test results in both CI extras, byte-level
   comparison against `main`, and any real-data run.

## Validation plan

- New tests fail on `main` and pass on the branch.
- The full suite passes in every CI extra.
- Every pre-existing export file is byte-identical to `main`'s output for
  the same input.
- LeRobot 0.3.3 loads v2.1/GR00T exports and LeRobot ≥ 0.6 loads v3.0
  exports.
- An export of a merged dataset maps every episode back to its input
  dataset and original id.

## Limitations and dependencies

- I do not have OpenArm hardware. Validation uses the repository fixtures
  unless the team shares a real recording.
- Isaac-GR00T's own loader has not been tested. GR00T compatibility rests
  on the export being LeRobot v2.1 with an unchanged `modality.json`.
- Items 1 and 3 depend on maintainer decisions. The schedule assumes
  answers within the first day.
