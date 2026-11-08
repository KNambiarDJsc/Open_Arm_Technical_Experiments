# Upstream PR draft (not opened)

Optional. Open only with the applicant's approval, and preferably after a
maintainer has said they want this design (see "Questions"). Format
follows `.github/copilot-instructions.md`: first line `Fix GH-71`, no
"Changes" section. The `research/` directory is not part of the PR; the PR
would contain only `src/`, `tests/test_provenance.py` and `README.md`.

---

**Title:** Record OpenArm provenance in the LeRobot/GR00T exports

Fix GH-71

The LeRobot v2.1, v3.0 and GR00T writers keep only the task prompt from
`metadata.yaml`. Episode ids, equipment and leader versions, task
descriptions and the effect of `--success-only`/`--valid-only` are lost,
so an export cannot be traced back to its recordings. For example, a
`--success-only` and a `--valid-only` export of the same dataset can have
identical `episodes.jsonl` files while containing different recordings.

This adds `meta/openarm.json` to those three outputs:

- `source`: format version, `operation_type`, `equipment`, `frequencies`,
  `tasks` (prompt and description), `num_episodes`. A field absent in the
  source is absent here (`operation_type` is not defaulted to `teleop`).
- `conversion`: `fps`, `smoothing_cutoff`, `state`, `arm_dynamics`,
  `success_only`, `valid_only`.
- `episodes`: for each exported `episode_index`, its exported `task_index`
  and the source episode's `id`, position in `metadata.yaml`, `success`,
  `task_index` and `valid`.
- `withheld`: names of source fields not exported.

`operator` and `location` are written only with
`--include-sensitive-metadata` (`include_sensitive_metadata=True`), since
these exports are often pushed to the Hub. Fields the package does not
know are never copied, only named in `withheld`.

No existing output file changes. I exported the same dataset with `main`
and with this branch in all three formats, with and without each filter,
and every data parquet, video and metadata file was byte-identical apart
from the new file. A sidecar was chosen over native fields because
lerobot 0.7.0 drops unknown `info.json` keys and fails to load data
columns not declared in `features`; both loaders ignore the sidecar.
`openarm_dataset.provenance.load_provenance()` reads and checks it.

Tested:

- `tests/test_provenance.py` (78 cases): mapping under each filter, with
  non-contiguous and duplicate ids, checked against the exported frames;
  privacy default and opt-in; unknown fields; 0.1.0 and unversioned
  sources; YAML dates; unrepresentable values fail before anything is
  written; failed conversions write no sidecar; deterministic output;
  malformed sidecars rejected; LeRobot loads the outputs; CLI.
- Full suite on Linux with the `lerobot-dataset-v3.0` extra (lerobot
  0.7.0): 368 passed, 7 skipped (missing optional extras / ffprobe).
  The v2.1/GR00T cases were run on Windows with lerobot 0.3.3; I have not
  run the `lerobot-dataset-v2.1` extra on Linux.

Not tested: Isaac-GR00T's own loader, real hardware recordings.

Questions:

1. Should `operator`/`location` be exported by default?
   `openarm-dataset-upload` already shows them on the dataset card.
2. Is `meta/openarm.json` the right name?
3. Should the source episode id also be added to `episodes.jsonl` / the
   v3.0 episodes parquet? Both LeRobot versions tolerate an extra
   per-episode field.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
