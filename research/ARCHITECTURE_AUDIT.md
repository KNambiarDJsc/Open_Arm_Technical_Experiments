# Architecture audit: how metadata and episode identity move through conversion

Repository: https://github.com/enactic/openarm_dataset
Audited revision: `3d291fe8a71153de03d76ca9a70c4fdb88fc1929` (`main`,
2026-11-04, "Add more checks for validation (#80)"). Line numbers below
refer to that revision unless marked "branch".
Package version: `0.4.0`, `requires-python >= 3.10`, Apache-2.0.

## 1. Environment used

| | Windows 11 | WSL2 Ubuntu |
|---|---|---|
| Python | 3.12.11 (uv-managed, as CI uses `uv sync -p 3.12`) | 3.12.3 |
| Install | `uv sync -p 3.12 --extra lerobot-dataset-v2.1` | `uv pip install -e ".[lerobot-dataset-v3.0]"` + CPU torch |
| lerobot / torch | 0.3.3 / 2.7.1 | 0.7.0 / 2.15.0+cpu |
| ffmpeg | n9.0.2 binary from `imageio-ffmpeg` (no `ffprobe`) | same |
| Used for | LeRobot v2.1, GR00T, CLI, lint | LeRobot v3.0, full suite on the CI OS |

No `uv.lock` is committed, so dependency versions are whatever resolved on
2026-11-08. CI (`.github/workflows/test.yaml`) runs on `ubuntu-latest`
once per extra. No type checker is configured; lint is `ruff` 0.14.11 via
pre-commit (`ruff check --fix`, `ruff format`) plus `shfmt`.

### Upstream test status before any change

- Windows, lerobot 0.3.3: 250 passed, 33 failed, 10 errors, 4 skipped.
  Every failure is Windows-specific and none touches v2.1/GR00T/convert:
  `lerobot_v30._write_packed_parquet` reopens a `NamedTemporaryFile` by name
  (impossible on Windows, `PermissionError`), `test_merge_with_symlink`
  needs the symlink privilege, `repair` hits the same temp-file pattern,
  and `validate` messages use `\` separators where the tests expect `/`.
- Linux: the upstream suite was not run separately before the change;
  after the change the full suite passes on Linux (368 passed, 7 skipped),
  which includes every upstream test.

## 2. Supported export formats and dispatch

`Dataset.write(output, format=..., **options)` (`dataset.py:716-748`)
dispatches on `format`:

| `format` | writer | metadata written |
|---|---|---|
| `None` / `openarm` | `Dataset._write` → `Metadata.write` (`metadata.py:158`) | the full `metadata.yaml`, version-upgraded to 0.4.0 |
| `lerobot_v2.1` | `lerobot_v21.to_lerobotv21` (`lerobot_v21.py:789`) | `meta/{info.json, episodes.jsonl, episodes_stats.jsonl, stats.json, tasks.jsonl}` |
| `lerobot_v3.0` | `lerobot_v30.to_lerobotv30` (`lerobot_v30.py:588`) | `meta/{info.json, stats.json, tasks.parquet, episodes/chunk-000/file-000.parquet}` |
| `gr00t` | `lerobot_v21.to_gr00t` (`lerobot_v21.py:862`) | LeRobot v2.1 + `meta/modality.json` (`lerobot_v21.py:891`) |
| `robot_eval_logger` | `robot_eval_logger.to_robot_eval_logger` | its own `metadata.json`, `location` from a CLI flag (`robot_eval_logger.py:328`), not from the source |
| `rrd` | `rrd.to_rrd` | rerun recording |

The CLI `openarm-dataset-convert` (`convert.py`) maps flags to these
keyword arguments and rejects flags that do not apply to the chosen format
with `parser.error`.

## 3. Source metadata model

`metadata.yaml` (format 0.4.0, see README "Dataset format") holds
`version`, `operator`, `location`, `operation_type`, `tasks[]`
(`prompt`, `description`), `episodes[]` (`id`, `success`, `task_index`,
optional `valid`), `equipment` (`id`, `version`, `embodiments`,
`perceptions.cameras`, optional `leader`) and `frequencies`.

`Metadata` (`metadata.py:65`) reads it:

- Unversioned datasets wrap everything in `meta:` and keep episodes in a
  separate `episodes.jsonl`; `__init__` flattens them (`metadata.py:73`).
  Their equipment has a different shape and is normalised on every access
  of `Metadata.equipment` by `_convert_unversioned_equipment`
  (`metadata.py:135`), which keeps `id`, `version`, an `arms` embodiment
  and the camera names, and drops the leader/follower arm details.
- `Metadata.operation_type` returns `"teleop"` when the field is absent
  (`metadata.py:99`). Formats before 0.2.0 do not record it, so reading it
  through the property would fabricate a value.
- `Episode.valid()` treats a missing `valid` flag as valid.
- `Metadata.episodes` returns views; the list position of an episode is
  not stored anywhere, it is only the index into this list.

## 4. Episode identity through an export

```
metadata.yaml episodes[]          records (lerobot_v21.py:160-187)      export
---------------------------       --------------------------------      ----------------------
pos 0  id "ep-0042"  success F ─┐  filtered by success_only/valid_only
pos 1  id "ep-0007"  valid F   ─┼─▶ [(pos, num_frames, obs, act, cams)] ─▶ _build_remaps:
pos 2  id "ep-0100"            ─┘   pos only; the id is never read        pos → 0..n-1
                                    except to locate files
                                    (dataset.py:262)
```

1. `_collect_downsampled_records` (`lerobot_v21.py:139-207`) iterates
   `enumerate(dataset.meta.episodes)`, skips episodes by `success_only`
   (line 161) and `valid_only` (line 163), samples the rest at `fps` and
   appends `(episode_index, num_frames, obs, actions, cameras)`. Here
   `episode_index` is the **list position**, not the `id`.
2. `_build_remaps` (`lerobot_v21.py:229-249`) maps list position →
   `0..n-1` in record order (line 237) and used source task indices →
   `0..m-1`, sorted.
3. All writers then use only the remapped indices:
   - v2.1: `_write_parquet` (`episode_index` column), `_write_videos` (file
     names), `_write_metadata` (`episodes.jsonl` line 573, `tasks.jsonl`
     line 587, `info.json` line 723).
   - v3.0: `_write_packed_parquet`, `_write_packed_videos`,
     `_write_episodes_and_stats` (`lerobot_v30.py:391`, episodes parquet),
     `_write_tasks_parquet` (line 470), `_write_info_json` (line 489).
   - GR00T: the v2.1 writer, then `_write_modality_json`, whose only
     annotation is `task_index`.
4. The source `id` is read only to locate files
   (`Dataset.episode_path`, `dataset.py:262`). It is never written.

Result: exported episode `k` is "the k-th episode that survived the
filters". The mapping exists in memory during the conversion and is
discarded. With non-contiguous ids (`"0"`, `"3"` in every repository
fixture) the exported index does not even equal the id when nothing is
filtered.

### Filters change the mapping, and the export cannot tell

Measured (`research/evidence/survey_baseline.md`, `research/scripts/survey_exports.py`):
on a three-episode source, the `success_only` export contains positions
1 and 2, and the `valid_only` export contains positions 0 and 2. Both
exports have two episodes with the same task and length, and their
metadata files have the same structure. Nothing in either says which
recordings they contain.

## 5. Field-by-field fate (baseline)

From the survey, identical in v2.1, v3.0 and GR00T, under every filter:

| source | fate | where |
|---|---|---|
| `tasks[].prompt` | preserved | `tasks.jsonl` / `tasks.parquet`; episode table `tasks` |
| `episodes[].success` | preserved per frame | data column `success` |
| `episodes[].task_index` | transformed (renumbered) | data column `task_index` |
| list position | transformed (renumbered) | `episode_index` |
| embodiment joint layout, camera names | transformed into feature names | `info.json` `features` |
| `frequencies` | replaced by the export `fps` | `info.json` `fps` |
| `episodes[].id` | discarded | - |
| `episodes[].valid` | used as a filter, discarded | - |
| `version`, `operation_type` | discarded | - |
| `equipment.id`, `equipment.version` | discarded | - |
| `equipment.embodiments.*` ids, versions, lifter geometry | discarded | - |
| `equipment.leader.*` device id, firmware, hardware version | discarded | - |
| `equipment.perceptions.cameras.*` per-camera config | discarded (names kept) | - |
| `tasks[].description` | discarded | - |
| `operator`, `location` | discarded | - |
| unknown fields | discarded | - |
| conversion options (`smoothing_cutoff`, `state`, filters) | not recorded | - |
| `robot_type` | constant `"openarm_bimanual"` (`lerobot_v21.py:31`), not derived from equipment | `info.json` |

Every export still loads in its LeRobot loader; the loss is of
provenance, not of tensors.

## 6. Related code paths

- `merge.merge_datasets` refuses inputs whose `equipment` differs
  (`merge.py:72-94`), so the project already treats equipment as identity.
  It also renumbers merged episode ids to `"0", "1", ...`
  (`merge.py:135`) and records nothing about which input an episode came
  from. Provenance is therefore already lost at merge time, before any
  export. This branch does not change that.
- `openarm-dataset-upload` embeds `metadata.yaml` verbatim on the Hugging
  Face dataset card (`upload.py:76`), including `operator` and `location`.
  So the project already publishes those fields for OpenArm-format
  uploads. This matters for the privacy default (PROVENANCE_DESIGN.md
  section 6).
- `Metadata.write(valid_only=True)` filters episodes but keeps their ids,
  so the OpenArm format keeps identity.

## 7. Adjacent defect found during the audit (not GH-71)

`_write_metadata` samples `dataset.meta.episodes[0]` to read camera shapes
for `info.json` (`lerobot_v21.py:683`), even when filters excluded that
episode. `_write_info_json` in v3.0 uses the first exported record
(`lerobot_v30.py:530`). If the excluded first episode is invalid because a
camera is missing, a `valid_only` export to v2.1 or GR00T raises
`IndexError` after the data parquet and videos have been written.
Reproduced on Windows and Linux with
`research/scripts/repro_v21_first_episode.py`; v3.0 is unaffected. It is
outside this branch's scope and is not fixed here.

## 8. What changed on the branch

| file | change |
|---|---|
| `src/openarm_dataset/provenance.py` (new) | builds, writes and reads `meta/openarm.json` |
| `src/openarm_dataset/lerobot_v21.py` | `to_lerobotv21`: build the record after `_build_remaps`, write it last; `to_gr00t` passes the option through; new keyword `include_sensitive_metadata=False` |
| `src/openarm_dataset/lerobot_v30.py` | same for `to_lerobotv30` |
| `src/openarm_dataset/convert.py` | `--include-sensitive-metadata`, rejected for other formats |
| `README.md` | documents the file and the flag |
| `tests/test_provenance.py` (new) | 78 test cases |

No existing function changes its behaviour and no existing output file
changes (verified byte for byte, `research/evidence/compare_exports.md`).
