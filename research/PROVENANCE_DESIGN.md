# Provenance design for the LeRobot/GR00T exports (GH-71)

Status: implemented on branch `research/openarm-dataset-provenance`, not
reviewed by Enactic. Upstream base: `3d291fe` (2026-11-04).

## 1. Problem

`to_lerobotv21`, `to_lerobotv30` and `to_gr00t` keep the metadata needed to
build tensors (task prompt, per-episode `success`, joint and camera layout)
and drop everything else in `metadata.yaml`. The baseline survey
(`research/scripts/survey_exports.py`, evidence in `research/evidence/`)
found, on all three formats and under every filter:

| source field | survives? |
|---|---|
| `tasks[].prompt` | yes, `tasks.jsonl`/`tasks.parquet` and the episode table |
| `episodes[].success` | yes, per-frame `success` column |
| camera names, joint layout | yes, as feature names in `info.json` |
| `episodes[].id` | **no** |
| `episodes[].valid` | **no** (applied as a filter, then forgotten) |
| `episodes[].task_index` | transformed: renumbered to be contiguous |
| list position of the episode | transformed: renumbered to be contiguous |
| `version` | **no** |
| `operation_type` | **no** |
| `equipment.id`, `equipment.version` | **no** |
| `equipment.embodiments.*` (ids, versions, lifter geometry) | **no** |
| `equipment.leader.*` (device id, firmware, hardware version) | **no** |
| `equipment.perceptions.cameras.*` (per-camera config) | **no** (names only) |
| `frequencies` | **no** (replaced by the export `fps`) |
| `tasks[].description` | **no** |
| `operator`, `location` | **no** |
| unknown top-level fields | **no** |
| conversion options (`smoothing_cutoff`, `state`, `success_only`, `valid_only`) | **no** |

The episode problem is the sharpest. Exported episode `k` is the `k`-th
episode that survived filtering. With `success_only=True` and
`valid_only=True` on the same source, the two exports have metadata of the
same shape (two episodes, the same task, the same lengths) but contain
different source episodes, and nothing in either export says which.

## 2. Requirements

1. Every training export records which source episode each exported
   episode came from, correctly under `success_only`/`valid_only` and with
   non-contiguous, unsorted or duplicated source ids.
2. Dataset-level identity: format version, equipment (including embodiment
   and leader versions), recording frequencies, operation type, tasks.
3. The conversion options that make this export differ from another export
   of the same recording.
4. The same structure for LeRobot v2.1, v3.0 and GR00T.
5. No change to tensors, feature names, joint order, data parquet, videos
   or any existing metadata file.
6. Operator and location are not exported unless asked for; fields whose
   sensitivity is unknown are not exported at all.
7. Nothing is invented: a field absent in the source is absent in the
   export.
8. Deterministic output; a malformed record is detectable by a reader.

## 3. Where to put it: options evaluated

The deciding facts come from `research/evidence/loader_tolerance.md`
(lerobot 0.3.3 for v2.1, lerobot 0.7.0 for v3.0, run on upstream code):

| extension | v2.1 loader | v3.0 loader |
|---|---|---|
| extra top-level key in `info.json` | loads, visible | loads, **silently dropped** from `ds.meta.info` |
| extra per-episode field (`episodes.jsonl` key / episodes parquet column) | loads, visible | loads, visible |
| extra data parquet column not declared in `features` | loads | **fails to load** |
| separate file `meta/openarm.json` | loads | loads |

**A. Native extension fields only.** Data parquet columns are ruled out:
they break the v3.0 loader, and a constant string per frame would bloat
the data anyway. An `info.json` key is ruled out: lerobot 0.7.0 parses
`info.json` into a typed object and drops unknown keys, so the key would
vanish from any dataset re-saved through LeRobot. A per-episode field works
in both LeRobot versions, but dataset-level identity (equipment, tasks,
frequencies, conversion options) has no per-episode home, and repeating it
on every episode row is redundant. Isaac-GR00T's reader of
`episodes.jsonl` was not tested.

**B. A versioned sidecar file, `meta/openarm.json`.** One schema for all
three formats, written by one helper. Both LeRobot loaders ignore it
(verified). Every existing file stays byte-identical (verified,
`research/evidence/compare_exports.md`). The cost: a consumer has to know the
file exists, and a tool that rebuilds `meta/` from scratch will not carry
it forward.

**C. Sidecar plus a per-episode native source id.** Adds discoverability
through `ds.meta.episodes` at the cost of a second copy of the mapping and
a change to existing files (`episodes.jsonl`, episodes parquet). It also
touches the file Isaac-GR00T reads, which could not be tested here.

**Decision: B.** It meets every requirement with no change to existing
files, and it is the only option verified against both LeRobot loaders
without caveats. C is a reasonable follow-up if maintainers want the source
id visible through LeRobot's API; it can be added later without changing
the sidecar schema. The choice was made from the loader evidence above. A
separate Patch Hiring proposal on the issue (H3Xobit, 2026-10-09) also
proposes `meta/openarm.json`; the two were arrived at independently, and
the differences are listed in section 9.

## 4. Schema (version 1)

```json
{
    "schema_version": 1,
    "generator": {"name": "openarm_dataset", "version": "0.4.0"},
    "source": {
        "version": "0.4.0",
        "operation_type": "teleop",
        "frequencies": {"action": {}, "cameras": {}, "obs": {}},
        "equipment": {"id": "...", "version": "...", "embodiments": {}, "perceptions": {}, "leader": {}},
        "tasks": [{"prompt": "...", "description": "..."}],
        "num_episodes": 3
    },
    "conversion": {
        "fps": 30, "smoothing_cutoff": 1.0, "state": "qpos",
        "arm_dynamics": false, "success_only": true, "valid_only": false
    },
    "withheld": ["location", "operator"],
    "episodes": [
        {"episode_index": 0, "task_index": 0,
         "source": {"index": 1, "id": "3", "success": true, "task_index": 0, "valid": true}}
    ]
}
```

Field rules:

| source field | in the sidecar |
|---|---|
| `version` | `source.version`; `null` for an unversioned dataset (that is what the package reports for it) |
| `operation_type`, `frequencies` | copied when present, **omitted when absent**. `Metadata.operation_type` defaults to `"teleop"`; the sidecar reads the raw field so the default is not recorded as fact |
| `equipment` | the whole tree as this package reads it (`Metadata.equipment`), i.e. unversioned datasets are normalised the same way the export itself is built. Copied verbatim, including nested keys this package does not know |
| `tasks[]` | `prompt` and `description` only |
| `episodes[]` (exported only) | `id`, `success`, `task_index`, `valid`, each only when present, plus `index`, the position in `metadata.yaml` |
| `operator`, `location` | only with `include_sensitive_metadata=True` (`--include-sensitive-metadata`) |
| any other top-level, task or episode field | never copied; its name is listed in `withheld` |

`withheld` lists, sorted, the names of fields that exist in the source but
are not in this export: `operator`/`location` when not opted in, unknown
top-level keys, and `tasks[].<key>`/`episodes[].<key>` for unknown keys of
tasks and exported episodes. So a reader can tell "absent in the source"
(key missing, not withheld) from "present but not exported" (named in
`withheld`). Names only, never values.

## 5. Episode mapping semantics

- `episodes` lists exported episodes only, in export order;
  `episode_index` is `0..n-1` and equals the LeRobot `episode_index`.
- `source.index` is the position in `metadata.yaml`'s `episodes` list. It
  is unique even when ids are not, so duplicated ids remain unambiguous.
- `source.id` is the episode directory name (`episodes/<id>/`).
- `task_index` is the exported (renumbered) task index; `source.task_index`
  is the original. The exported index resolves through `tasks.jsonl` or
  `tasks.parquet` to the same prompt as `source.tasks[source.task_index]`.
- Filtered-out episodes are not listed, by id or otherwise. Their number
  can be derived as `source.num_episodes - len(episodes)`; `conversion`
  says which filters ran.

## 6. Privacy

`operator` names a person; `location` can name a site. Both are withheld by
default because LeRobot datasets are routinely pushed to the Hugging Face
Hub, and the sidecar would go with them. Fields this package does not know
are withheld even with the opt-in, because nothing says whether they are
sensitive.

Two caveats a reviewer should weigh:

- `equipment` is copied verbatim. In every format version it describes
  hardware (ids, versions, geometry). If a lab puts serial numbers or other
  internal identifiers there, they are exported. Allowlisting nested keys
  was rejected because it would silently drop new hardware fields, which is
  exactly the loss this change exists to fix.
- `openarm-dataset-upload` already publishes `metadata.yaml`, including
  `operator` and `location`, verbatim on the dataset card for OpenArm-format
  datasets. Maintainers may therefore prefer the opposite default. The
  opt-in is one keyword; flipping the default is a one-line change.

Pseudonymising the operator with a hash was rejected: operator sets are
small, so a hash is reversible by trying the candidates.

## 7. No metadata hash

A hash of `metadata.yaml` was considered and left out.

- Raw-byte hash: changes on any reformatting, and on
  `openarm-dataset-validate`, which rewrites the file to add `valid` flags.
  It can confirm "this exact file", nothing more.
- Canonical hash (parsed, key-sorted JSON): stable under reformatting,
  still changed by validation.
- Neither covers the episode data (parquet, JPEG), so neither says anything
  about the integrity of the recording or of the export.
- With `operator`/`location` withheld, a hash over the full metadata is a
  side channel: every other field is in the sidecar, so a short list of
  candidate operators and sites can be tested against the hash.
- With everything included, the sidecar already contains the hashed
  content.

A content hash of the episode data would be a real integrity feature, but
it is a separate one, it costs a full read of every recording, and it is
not what the issue asks for.

## 8. Serialization and failure behaviour

- JSON, `indent=4`, `ensure_ascii=False` (the style of the other `meta/`
  writers), LF line endings on every OS, keys in a fixed order. No
  timestamps, so the same input and options give byte-identical output.
- YAML dates (`!!timestamp`) become ISO 8601 strings. Bytes (`!!binary`)
  and non-finite floats cannot be represented in strict JSON; the
  conversion fails with a `ValueError` naming the field. The sidecar is
  built after the episodes are sampled but before any file is written, so
  this failure leaves no partial output.
- The sidecar is written last, so a conversion that fails part-way does
  not leave a provenance record. (For GR00T, `modality.json` is written
  after the LeRobot v2.1 part, so a failure in `modality.json` leaves a
  sidecar next to an incomplete GR00T export, exactly as it already leaves
  `info.json`.)
- `openarm_dataset.provenance.load_provenance(path)` reads the sidecar and
  raises `ValueError` if the schema version is unknown, a required key is
  missing or mistyped, `episode_index` is not `0..n-1` in order, a
  `source.index` repeats, or the episode count disagrees with
  `meta/info.json`.

## 9. Rejected or deferred alternatives

| alternative | why not (now) |
|---|---|
| Copy `metadata.yaml` verbatim into `meta/` | publishes operator, location and unknown fields; does not record the export mapping |
| Provenance key in `info.json` | dropped by lerobot 0.7.0 |
| Per-frame provenance columns in the data parquet | breaks the lerobot 0.7.0 loader; changes training files |
| Per-episode native source id (option C) | viable, deferred: changes existing files, GR00T reader untested |
| GR00T annotation channel for the equipment (proposed by H3Xobit) | a training feature, not provenance; changes the parquet and `modality.json`; needs a maintainer decision on how GR00T should consume it |
| A separate schema per format | three schemas to keep aligned for no gain; the sidecar's content does not depend on the LeRobot layout |
| Record the output `format` in the sidecar | redundant with `info.json`'s `codebase_version` and the presence of `modality.json`, and would force a second code path for GR00T |
| Metadata hash | see section 7 |

Differences from the H3Xobit proposal, for reviewers comparing them: that
proposal exports operator and location by default, records no per-episode
source mapping, and adds a GR00T annotation column. This branch withholds
operator/location by default, records the full source-to-export episode
mapping and conversion options, lists withheld fields, and changes no
existing file.

## 10. Questions for maintainers

1. Should operator/location be exported by default, given that
   `openarm-dataset-upload` already publishes them?
2. Is `meta/openarm.json` an acceptable name and location?
3. Should the source episode id also appear in the native episode table
   (option C)?
4. Is the GR00T equipment annotation channel wanted as a separate change?
