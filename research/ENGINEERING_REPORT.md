# Engineering report: GH-71 provenance in the LeRobot/GR00T exports

Branch `research/openarm-dataset-provenance`, based on upstream `3d291fe`.
Work done 2026-11-08, independently, without maintainer involvement and
without OpenArm hardware. Nothing has been pushed or posted upstream.

## What was implemented

- `meta/openarm.json` (schema version 1) written by `to_lerobotv21`,
  `to_lerobotv30` and `to_gr00t` through one shared module,
  `src/openarm_dataset/provenance.py`. It records the source format
  version, operation type, equipment, frequencies, tasks with descriptions
  and episode count; the conversion options; the exported-to-source
  mapping of every episode; and the names of withheld fields.
- `operator`/`location` withheld unless `include_sensitive_metadata=True`
  or `--include-sensitive-metadata`; unknown fields never copied, only
  named.
- `load_provenance(path)`, which rejects malformed records.
- README section; 78 regression tests; five research scripts; evidence.

## What was not implemented

- Any training use of the metadata (the issue's last sentence). No GR00T
  annotation channel, no hardware conditioning.
- A native per-episode source id in `episodes.jsonl`/episodes parquet
  (design option C). Viable, deferred for a maintainer decision.
- Provenance through `openarm-dataset-merge`, which renumbers ids and
  forgets which input each episode came from.
- `robot_eval_logger` and `rrd` exports.
- A fix for the adjacent `valid_only` crash (ARCHITECTURE_AUDIT.md
  section 7). It is reproduced, not fixed.

## Goals and status

| goal | status | evidence |
|---|---|---|
| Reproduce on a recorded upstream commit | done, `3d291fe` | `evidence/survey_baseline.md`, `evidence/tests_before_fix_*` |
| Check for overlapping work | done. No implementation exists; one open Patch Hiring proposal (H3Xobit, 2026-10-09) on the issue proposes the same sidecar name | `gh issue view 71`, fork scan |
| Integrated in the real export paths | done, all three formats | `lerobot_v21.py`, `lerobot_v30.py` |
| Verified source-to-export episode mapping | done, including filters, non-contiguous and duplicate ids; mapping checked against exported frame data | `test_episode_mapping`, `test_mapping_matches_exported_data` |
| Documented contract | done | `PROVENANCE_DESIGN.md`, README |
| Deliberate privacy handling | done (default withheld, opt-in, unknown fields never copied) | `test_sensitive_*`, `test_unknown_*` |
| Existing schema unchanged | done, byte-identical outputs | `evidence/compare_exports.md` |
| Existing and new tests pass | done on Linux (CI OS); Windows has pre-existing platform failures only | `evidence/tests_after_fix_*` |
| Downstream loader per format | LeRobot v2.1 (0.3.3), v3.0 (0.7.0), GR00T export via LeRobot 0.3.3; **Isaac-GR00T's own loader not tested** | `test_lerobot_loads_export_with_provenance`, `evidence/cli_walkthrough_gr00t.txt` |

## Test results

| suite | environment | before | after |
|---|---|---|---|
| `tests/test_provenance.py` (v2.1 + GR00T, 60 cases) | Windows, lerobot 0.3.3 | 52 failed, 8 passed | 60 passed |
| `tests/test_provenance.py` (v3.0, 18 cases) | WSL2 Ubuntu, lerobot 0.7.0 | 15 failed, 3 passed | 18 passed |
| full suite | WSL2 Ubuntu, lerobot 0.7.0 | not run | 368 passed, 7 skipped* |
| full suite | Windows, lerobot 0.3.3 | 250 passed, 33 failed, 10 errors, 4 skipped | 313 passed, 47 failed, 10 errors, 5 skipped |
| `ruff check`, `ruff format --check` (0.14.11) | Windows | - | pass |
| wheel build (`uv build --wheel`) | Windows | - | includes `provenance.py` |

\* Includes all 78 `test_provenance` cases: 76 passed, and the v2.1 and
GR00T loader cases skipped because they need lerobot < 0.5 (they pass on
Windows with lerobot 0.3.3).

The 8 + 3 cases that pass before the change are guards (no sidecar after
a failed conversion; the CLI rejects the flag for other formats). The 14
additional Windows failures after the change are the new v3.0 cases, which
hit the same pre-existing `NamedTemporaryFile` limitation
(`lerobot_v30.py:134`) as upstream's own v3.0 tests. The 43 other Windows
failures and errors are the upstream baseline's, unchanged.

Seven skips in the Linux run, all environmental: `lz4` and `rerun`
extras not installed; two upstream v2.1 load tests and two new loader
tests need lerobot < 0.5; one upstream video-timestamp test needs
`ffprobe`, which the imageio-ffmpeg binary does not include.

## Challenges

- **The v3.0 writer does not run on Windows.** It writes a temporary
  parquet by name while the `NamedTemporaryFile` is open. All v3.0 work
  ran in WSL2.
- **WSL had no `python3-venv` and no sudo.** A standalone uv binary
  created the environment. CPU-only torch kept the install smaller.
- **Disk.** The WSL virtual disk lives on C: and grew by several GB during
  installs and the full test run. C: went from 13.4 GB to under 1 GB
  free at one point. Freed by deleting this session's pytest temp
  directories; later Windows runs used `--basetemp` on D:. The virtual
  disk itself can only be shrunk with administrator rights.
- **Designing a negative test.** The first regression test searches all
  export metadata for the source values, so it fails on upstream
  regardless of where a fix would put them. That is how the gap was shown
  to exist independently of this design.

## Architectural decisions

1. **Sidecar over native fields**, decided by measured loader behaviour:
   lerobot 0.7.0 drops unknown `info.json` keys and refuses undeclared data
   columns. Details in `PROVENANCE_DESIGN.md`.
2. **One shared builder**, called from the two writer functions; GR00T
   inherits it through `to_lerobotv21`.
3. **Build before writing, write last.** Bad metadata leaves no partial
   output, and a half-finished export carries no provenance claim.
4. **Allowlist at the top level, verbatim `equipment`.** The top level
   mixes personal and hardware fields. `equipment` is hardware by
   definition, and allowlisting inside it would drop future hardware
   fields silently.
5. **`withheld` names.** Absence is ambiguous without it.
6. **No metadata hash.** It is not an integrity proof, it changes with
   validation, and it is a side channel for withheld fields.
7. **No conversion timestamp or output format field.** Keeps output
   deterministic and avoids a second GR00T code path.

## Remaining risks

- Maintainers may want a different default for operator/location (the
  project's uploader already publishes them), a different file name, or
  the per-episode native id. All are small changes.
- `equipment` can contain whatever a lab writes there.
- `generator.version` comes from the installed package metadata, so a
  source checkout that is not installed records `null`.
- A GR00T export whose `modality.json` step fails leaves a sidecar next to
  an incomplete export, as it already leaves `info.json`.
- Tests run on the repository's small fixtures. Large datasets were not
  exercised, though the sidecar's size is linear in the number of
  episodes and it reads no episode data.

## Future work

In order of value: carry provenance through `merge`; fix the adjacent
`valid_only` crash; decide option C; an export verifier that re-samples
mapped source episodes; hardware-aware training use once identity
survives export.

## Engineering reflections

- The code change is small. The useful work was establishing exactly what
  is lost and what the loaders tolerate, so that the design is backed by
  measurements rather than preference.
- Byte-for-byte comparison against the upstream revision gave a stronger
  compatibility claim than the existing tests could. They check shapes and
  values, not that nothing else moved.
- Writing the privacy rules forced finding the `operation_type` default,
  which would have put a fabricated value into every pre-0.2.0 export.
- The overlap with an existing public proposal reduces the novelty of the
  core idea. The differences are in the episode mapping, the privacy
  handling and the verification.
- Nothing here was validated on hardware or on a real multi-rig corpus.
