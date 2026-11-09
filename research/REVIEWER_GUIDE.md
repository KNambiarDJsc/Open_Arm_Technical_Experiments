# Reviewer guide: GH-71 provenance branch

Branch `research/openarm-dataset-provenance` on top of upstream `3d291fe`.

## Where the code changed

```
src/openarm_dataset/provenance.py   new: build, write and read meta/openarm.json
src/openarm_dataset/lerobot_v21.py  to_lerobotv21: build after _build_remaps, write last;
                                    to_gr00t: pass include_sensitive_metadata through
src/openarm_dataset/lerobot_v30.py  to_lerobotv30: same as v2.1
src/openarm_dataset/convert.py      --include-sensitive-metadata (lerobot/gr00t only)
README.md                           section on meta/openarm.json
tests/test_provenance.py            new: 78 cases
research/                           audit, design, evidence, scripts, reports (not for upstream)
```

Review order: `provenance.py` (`build_provenance`, then `_source`, then
`_check`/`load_provenance`), the two call sites, then the tests.

## Why it exists

The LeRobot v2.1/v3.0 and GR00T exports keep only the task prompt from
`metadata.yaml`. Episode ids, equipment and leader versions, task
descriptions and the effect of `success_only`/`valid_only` are lost, so an
export cannot be traced to its recordings (issue #71). See
`ARCHITECTURE_AUDIT.md` sections 4-5.

## Minimal reproduction

```bash
uv sync -p 3.12 --extra lerobot-dataset-v2.1
uv run openarm-dataset-convert tests/fixture/dataset_0.4.0_qpos /tmp/out \
    --format gr00t --success-only
cat /tmp/out/meta/openarm.json
```

On upstream, `/tmp/out/meta/openarm.json` does not exist, and no file under
`/tmp/out/meta` records the equipment id, the leader firmware `1.2.3`, the
task description, or that exported episode 0 is source episode `"3"`. On
the branch, the file maps exported episode 0 to source
`{"index": 1, "id": "3", ...}`.

To see the gap on upstream itself:

```bash
git stash -u   # if needed
git checkout 3d291fe
uv run python research/scripts/survey_exports.py /tmp/survey lerobot_v2.1 gr00t
```

(The script lives on the branch; copy it out first, or run it with
`PYTHONPATH=<upstream checkout>/src`, as `compare_exports.py` does.)

## Running the tests

```bash
# Linux, as CI does, once per extra
uv sync -p 3.12 --extra lerobot-dataset-v2.1 && uv run pytest tests/test_provenance.py -rs
uv sync -p 3.12 --extra lerobot-dataset-v3.0 && uv run pytest tests/test_provenance.py -rs
uv run pytest -rs                                  # full suite
pre-commit run --all-files                         # ruff check + format
```

Loader tests skip themselves when the installed lerobot cannot read the
format (v2.1/GR00T need lerobot < 0.5, v3.0 needs >= 0.5). On Windows the
v3.0 cases fail for the same pre-existing temp-file reason as upstream's
own v3.0 tests; run them on Linux.

## Inspecting provenance

```python
from openarm_dataset.provenance import load_provenance
p = load_provenance("/tmp/out")          # raises ValueError if malformed
p["source"]["equipment"]                 # hardware as recorded
p["conversion"]                          # fps, smoothing, state, filters
[(e["episode_index"], e["source"]["id"]) for e in p["episodes"]]
p["withheld"]                            # fields present but not exported
```

## Confirming backward compatibility

```bash
git worktree add /tmp/upstream 3d291fe
PYTHONPATH=/tmp/upstream/src uv run python research/scripts/compare_exports.py export /tmp/a lerobot_v2.1 gr00t
uv run python research/scripts/compare_exports.py export /tmp/b lerobot_v2.1 gr00t
uv run python research/scripts/compare_exports.py compare /tmp/a /tmp/b
```

Expected: every file identical, `meta/openarm.json` added, exit code 0.
Use `lerobot_v3.0` on Linux. Recorded results:
`evidence/compare_exports.md`. Also `test_only_the_sidecar_is_added`
(file list, data columns) and the existing `test_gr00t.py`
(`modality.json` unchanged).

## Decisions a reviewer may want to change

| decision | where | to change |
|---|---|---|
| operator/location withheld by default | `include_sensitive_metadata=False` | flip the default |
| file name `meta/openarm.json` | `PROVENANCE_PATH` | one constant |
| unknown fields never copied | `_source`, `_episode` | widen the allowlists |
| no native per-episode id | - | add a key to `episodes.jsonl`/episodes parquet (loaders tolerate it) |

## Claims that remain unverified

- Isaac-GR00T's own data loader reading the GR00T export with the sidecar
  present. Only LeRobot 0.3.3 was used.
- Any behaviour on real hardware recordings or large datasets; only the
  repository fixtures were exported.
- lerobot versions other than 0.3.3 and 0.7.0.
- The full upstream suite on Linux *before* the change was not run
  separately. The after-change run passes every upstream test.
- macOS.
