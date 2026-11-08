# Copyright 2026 Enactic, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Provenance of a LeRobot v2.1/v3.0 or GR00T export.

Every training export writes ``meta/openarm.json``: the OpenArm metadata the
LeRobot layout has no place for (equipment, frequencies, task descriptions,
...), the conversion options, and which source episode each exported
episode came from. No other file of the export is changed.

Fields this package does not know are never copied, and ``operator`` and
``location`` only on request; the names of fields left out are listed in
``withheld`` so that "not recorded" and "not exported" can be told apart.
"""

from __future__ import annotations

import datetime
import json
import math
from importlib import metadata as importlib_metadata
from pathlib import Path

SCHEMA_VERSION = 1
PROVENANCE_PATH = "meta/openarm.json"

# Top-level metadata.yaml fields copied as they are when present.
_COPIED_FIELDS = ("operation_type", "frequencies")
# Top-level fields that identify people or places: copied only on request.
SENSITIVE_FIELDS = ("operator", "location")
# Top-level fields exported in their own form below.
_HANDLED_FIELDS = ("version", "equipment", "tasks", "episodes")
_TASK_FIELDS = ("prompt", "description")
_EPISODE_FIELDS = ("id", "success", "task_index", "valid")


def _jsonable(value, path: str):
    """Return a JSON-representable copy of a YAML value.

    Dates become ISO 8601 strings; values strict JSON cannot represent
    (bytes, NaN, infinity, ...) raise ``ValueError`` naming the field.
    """
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if not isinstance(key, (str, int, float, bool)) or key is None:
                raise ValueError(f"{path}: key {key!r} cannot be written as JSON")
            result[str(key)] = _jsonable(child, f"{path}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [_jsonable(child, f"{path}[{i}]") for i, child in enumerate(value)]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path}: {value} cannot be written as JSON")
        return value
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    raise ValueError(
        f"{path}: a {type(value).__name__} value cannot be written as JSON"
    )


def _generator_version() -> str | None:
    try:
        return importlib_metadata.version("openarm_dataset")
    except importlib_metadata.PackageNotFoundError:
        return None


def _source(meta, include_sensitive_metadata: bool) -> tuple[dict, list[str]]:
    """Return the dataset-level part and the withheld top-level/task fields."""
    data = meta.data
    withheld = []
    source = {"version": meta.version}
    for field in _COPIED_FIELDS + SENSITIVE_FIELDS:
        if field not in data:
            continue
        if field in SENSITIVE_FIELDS and not include_sensitive_metadata:
            withheld.append(field)
            continue
        source[field] = _jsonable(data[field], field)
    # As this package reads it: unversioned datasets are normalised the same
    # way the export itself is built.
    source["equipment"] = _jsonable(meta.equipment._data, "equipment")
    if meta.tasks is not None:
        source["tasks"] = []
        for index, task in enumerate(meta.tasks):
            source["tasks"].append(
                {
                    field: _jsonable(task[field], f"tasks[{index}].{field}")
                    for field in _TASK_FIELDS
                    if field in task
                }
            )
            withheld.extend(f"tasks[].{k}" for k in task if k not in _TASK_FIELDS)
    source["num_episodes"] = meta.num_episodes
    known = _COPIED_FIELDS + SENSITIVE_FIELDS + _HANDLED_FIELDS
    withheld.extend(field for field in data if field not in known)
    return source, withheld


def _episode(meta, source_index: int, episode_index: int, task_index: int) -> dict:
    episode = meta.episodes[source_index]
    source = {"index": source_index}
    for field in _EPISODE_FIELDS:
        if field in episode:
            source[field] = _jsonable(
                episode[field], f"episodes[{source_index}].{field}"
            )
    return {"episode_index": episode_index, "task_index": task_index, "source": source}


def build_provenance(
    dataset,
    source_indices: list[int],
    remap_episode_index: dict[int, int],
    remap_task_index: dict[int, int],
    conversion: dict,
    include_sensitive_metadata: bool = False,
) -> str:
    """Return the provenance of an export as JSON text.

    Args:
        dataset: The exported ``Dataset``.
        source_indices: Positions in ``dataset.meta.episodes`` of the
            exported episodes, in export order.
        remap_episode_index: Source position to exported episode index.
        remap_task_index: Source task index to exported task index.
        conversion: The export options to record.
        include_sensitive_metadata: Also record ``operator`` and
            ``location``.

    Raises:
        ValueError: If the metadata holds a value JSON cannot represent.
            Called before any file is written, so nothing is left behind.

    """
    meta = dataset.meta
    source, withheld = _source(meta, include_sensitive_metadata)
    episodes = []
    for source_index in source_indices:
        episode = meta.episodes[source_index]
        episodes.append(
            _episode(
                meta,
                source_index,
                remap_episode_index[source_index],
                remap_task_index[int(episode["task_index"])],
            )
        )
        withheld.extend(f"episodes[].{k}" for k in episode if k not in _EPISODE_FIELDS)
    provenance = {
        "schema_version": SCHEMA_VERSION,
        "generator": {"name": "openarm_dataset", "version": _generator_version()},
        "source": source,
        "conversion": _jsonable(conversion, "conversion"),
        "withheld": sorted(set(withheld)),
        "episodes": episodes,
    }
    _check(provenance)
    return json.dumps(provenance, ensure_ascii=False, indent=4, allow_nan=False) + "\n"


def write_provenance(output_dir: str | Path, provenance: str) -> None:
    """Write JSON text from ``build_provenance`` to ``meta/openarm.json``."""
    path = Path(output_dir) / PROVENANCE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(provenance)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check(provenance, total_episodes: int | None = None) -> None:
    """Raise ``ValueError`` if ``provenance`` does not follow the schema."""
    if not isinstance(provenance, dict):
        raise ValueError("provenance must be a JSON object")
    version = provenance.get("schema_version")
    if not _is_int(version) or version != SCHEMA_VERSION:
        raise ValueError(f"unsupported provenance schema_version: {version!r}")
    for key, type_ in (
        ("source", dict),
        ("conversion", dict),
        ("withheld", list),
        ("episodes", list),
    ):
        if not isinstance(provenance.get(key), type_):
            raise ValueError(f"provenance {key!r} is missing or not a {type_.__name__}")
    seen = set()
    for position, episode in enumerate(provenance["episodes"]):
        where = f"provenance episodes[{position}]"
        if not isinstance(episode, dict) or not isinstance(episode.get("source"), dict):
            raise ValueError(f"{where} has no source")
        if episode.get("episode_index") != position or not _is_int(
            episode.get("episode_index")
        ):
            raise ValueError(
                f"{where} has episode_index {episode.get('episode_index')!r}"
            )
        if not _is_int(episode.get("task_index")):
            raise ValueError(f"{where} has no integer task_index")
        source = episode["source"]
        if not _is_int(source.get("index")) or not isinstance(source.get("id"), str):
            raise ValueError(f"{where} needs an integer source index and a string id")
        if source["index"] in seen:
            raise ValueError(f"{where} repeats source index {source['index']}")
        seen.add(source["index"])
    if total_episodes is not None and total_episodes != len(provenance["episodes"]):
        raise ValueError(
            f"provenance lists {len(provenance['episodes'])} episodes but the "
            f"dataset has {total_episodes}"
        )


def load_provenance(path: str | Path) -> dict:
    """Read and check the provenance of an exported dataset.

    Args:
        path: The root directory of a LeRobot v2.1/v3.0 or GR00T export.

    Returns:
        The parsed ``meta/openarm.json``.

    Raises:
        FileNotFoundError: If the export has no provenance file.
        ValueError: If the file is not valid JSON, does not follow the
            schema, or lists a different number of episodes than
            ``meta/info.json``.

    """
    root = Path(path)
    with (root / PROVENANCE_PATH).open(encoding="utf-8") as f:
        provenance = json.load(f)
    total_episodes = None
    info_path = root / "meta" / "info.json"
    if info_path.exists():
        with info_path.open(encoding="utf-8") as f:
            total_episodes = json.load(f).get("total_episodes")
    _check(provenance, total_episodes)
    return provenance
