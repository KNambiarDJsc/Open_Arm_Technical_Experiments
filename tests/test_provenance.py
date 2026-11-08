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

"""OpenArm metadata carried into the LeRobot/GR00T exports (GH-71)."""

from pathlib import Path
import copy
import datetime
import json
import shutil

import numpy as np
import packaging.version
import pandas as pd
import pytest
import yaml

from openarm_dataset import Dataset
from openarm_dataset.metadata import Metadata

FIXTURE_DIR = Path(__file__).parent / "fixture"
QPOS_FIXTURE = FIXTURE_DIR / "dataset_0.4.0_qpos"
FORMATS = ("lerobot_v2.1", "lerobot_v3.0", "gr00t")
FPS = 30

TASKS = [
    {"prompt": "Pick the cube.", "description": "Pick the red cube from the tray."},
    {"prompt": "Place the cube.", "description": "Place the cube on the shelf."},
]
# (source id, fixture episode, success, valid, task_index), in metadata order.
# The ids are neither contiguous nor sorted, and the first episode is the one
# both filters can remove.
EPISODES = [
    ("ep-0042", "0", False, True, 1),
    ("ep-0007", "3", True, False, 0),
    ("ep-0100", "3", True, True, 1),
]
OPERATOR = "Operator Alice"
LOCATION = "Lab B12"
UNKNOWN_FIELD_VALUE = "unclassified custom field"


def _write_source(root: Path, episodes=EPISODES, **overrides) -> Path:
    """Write a 0.4.0 dataset under ``root`` from the qpos fixture's episodes."""
    meta = yaml.safe_load((QPOS_FIXTURE / "metadata.yaml").read_text())
    meta["operator"] = OPERATOR
    meta["location"] = LOCATION
    meta["site_notes"] = UNKNOWN_FIELD_VALUE
    meta["equipment"]["id"] = "OpenArm-Rig-7"
    meta["equipment"]["version"] = "2.3"
    meta["equipment"]["leader"]["ker"]["firmware_version"] = "9.8.7"
    meta["tasks"] = copy.deepcopy(TASKS)
    meta["episodes"] = []
    for source_id, fixture_id, success, valid, task_index in episodes:
        destination = root / "episodes" / source_id
        if not destination.exists():
            shutil.copytree(QPOS_FIXTURE / "episodes" / fixture_id, destination)
        meta["episodes"].append(
            {
                "id": source_id,
                "success": success,
                "task_index": task_index,
                "valid": valid,
            }
        )
    meta.update(overrides)
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "metadata.yaml", "w") as f:
        yaml.safe_dump(meta, f)
    return root


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    return _write_source(tmp_path_factory.mktemp("source"))


@pytest.fixture(scope="module")
def export(tmp_path_factory, source):
    """Export ``source`` once per (format, options) for the whole module."""
    cache = {}

    def run(format_, **options):
        key = (format_, tuple(sorted(options.items())))
        if key not in cache:
            output = tmp_path_factory.mktemp("export")
            Dataset(source).write(output, format=format_, fps=FPS, **options)
            cache[key] = output
        return cache[key]

    return run


def _load(output: Path) -> dict:
    from openarm_dataset.provenance import load_provenance

    return load_provenance(output)


def _metadata_texts(output: Path) -> dict[str, str]:
    """Return every file the export wrote under ``meta/`` as searchable text."""
    texts = {}
    for path in sorted((output / "meta").rglob("*")):
        if path.is_dir():
            continue
        if path.suffix == ".parquet":
            texts[path.name] = pd.read_parquet(path).reset_index().to_json()
        else:
            texts[path.name] = path.read_text(encoding="utf-8")
    return texts


def _exported_tasks(output: Path) -> dict[int, str]:
    """Return the export's ``{task_index: prompt}`` table."""
    jsonl = output / "meta" / "tasks.jsonl"
    if jsonl.exists():
        rows = [json.loads(line) for line in jsonl.read_text().splitlines()]
        return {row["task_index"]: row["task"] for row in rows}
    df = pd.read_parquet(output / "meta" / "tasks.parquet")
    return {int(index): task for task, index in zip(df.index, df["task_index"])}


def _exported_frames(output: Path) -> pd.DataFrame:
    return pd.concat(
        [pd.read_parquet(p) for p in sorted((output / "data").rglob("*.parquet"))],
        ignore_index=True,
    )


def _total_episodes(output: Path) -> int:
    with open(output / "meta" / "info.json") as f:
        return json.load(f)["total_episodes"]


# --- The provenance gap itself (independent of where a fix stores it) ------


@pytest.mark.parametrize("format_", FORMATS)
def test_source_identity_survives_export(export, format_):
    text = "\n".join(_metadata_texts(export(format_)).values())
    for value in (
        "OpenArm-Rig-7",  # equipment.id
        "2.3",  # equipment.version
        "9.8.7",  # equipment.leader.ker.firmware_version
        "Pick the red cube from the tray.",  # tasks[0].description
        "ep-0042",  # episode ids
        "ep-0007",
        "ep-0100",
    ):
        assert json.dumps(value) in text, f"{value!r} is not in the export metadata"


# --- Dataset-level identity -------------------------------------------------


@pytest.mark.parametrize("format_", FORMATS)
def test_dataset_level_identity(export, source, format_):
    provenance = _load(export(format_))
    recorded = yaml.safe_load((source / "metadata.yaml").read_text())
    assert provenance["schema_version"] == 1
    assert provenance["generator"]["name"] == "openarm_dataset"
    origin = provenance["source"]
    assert origin["version"] == "0.4.0"
    assert origin["operation_type"] == "teleop"
    assert origin["equipment"] == recorded["equipment"]
    assert origin["frequencies"] == recorded["frequencies"]
    assert origin["tasks"] == TASKS
    assert origin["num_episodes"] == len(EPISODES)


@pytest.mark.parametrize("format_", FORMATS)
def test_conversion_options_recorded(export, format_):
    conversion = _load(export(format_))["conversion"]
    assert conversion == {
        "fps": FPS,
        "smoothing_cutoff": 1.0,
        "state": "qpos",
        "arm_dynamics": False,
        "success_only": False,
        "valid_only": False,
    }


def test_same_source_at_another_rate_keeps_source_identity(export):
    default = _load(export("lerobot_v2.1"))
    resampled = _load(export("lerobot_v2.1", smoothing_cutoff=0))
    assert resampled["source"] == default["source"]
    assert resampled["episodes"] == default["episodes"]
    assert resampled["conversion"]["smoothing_cutoff"] == 0
    assert default["conversion"]["smoothing_cutoff"] == 1.0


# --- Episode mapping --------------------------------------------------------

SELECTIONS = {
    "all": ({}, [0, 1, 2]),
    # success_only removes the first (earlier) source episode.
    "success_only": ({"success_only": True}, [1, 2]),
    # valid_only removes a middle one.
    "valid_only": ({"valid_only": True}, [0, 2]),
    "success_and_valid_only": ({"success_only": True, "valid_only": True}, [2]),
}


@pytest.mark.parametrize("selection", SELECTIONS)
@pytest.mark.parametrize("format_", FORMATS)
def test_episode_mapping(export, format_, selection):
    options, source_indices = SELECTIONS[selection]
    output = export(format_, **options)
    provenance = _load(output)
    episodes = provenance["episodes"]
    assert [e["episode_index"] for e in episodes] == list(range(len(source_indices)))
    assert [e["source"]["index"] for e in episodes] == source_indices
    assert len(episodes) == _total_episodes(output)
    tasks = _exported_tasks(output)
    for episode in episodes:
        source_id, _, success, valid, task_index = EPISODES[episode["source"]["index"]]
        assert episode["source"] == {
            "index": episode["source"]["index"],
            "id": source_id,
            "success": success,
            "task_index": task_index,
            "valid": valid,
        }
        # The exported task index resolves to the source episode's prompt.
        assert tasks[episode["task_index"]] == TASKS[task_index]["prompt"]
    conversion = provenance["conversion"]
    assert conversion["success_only"] == options.get("success_only", False)
    assert conversion["valid_only"] == options.get("valid_only", False)


@pytest.mark.parametrize("format_", FORMATS)
def test_filtered_episodes_are_not_listed(export, format_):
    output = export(format_, success_only=True, valid_only=True)
    text = (output / "meta" / "openarm.json").read_text()
    assert "ep-0100" in text
    assert "ep-0042" not in text
    assert "ep-0007" not in text


@pytest.mark.parametrize("format_", FORMATS)
def test_mapping_matches_exported_data(export, source, format_):
    # valid_only keeps ep-0042 (fixture episode 0) and ep-0100 (fixture
    # episode 3), whose recordings differ, so a swapped mapping is detected.
    output = export(format_, valid_only=True)
    frames = _exported_frames(output)
    dataset = Dataset(source)
    dataset.set_smoothing(1.0)
    keys = ("arms/right/qpos", "arms/left/qpos", "lifter/elevation")
    first_actions = []
    for episode in _load(output)["episodes"]:
        rows = frames[frames["episode_index"] == episode["episode_index"]]
        samples = dataset.sample(
            FPS, episode=dataset.meta.episodes[episode["source"]["index"]]
        )
        assert len(rows) == len(samples)
        expected = np.concatenate([samples[0].action[k] for k in keys])
        np.testing.assert_allclose(rows["action"].iloc[0], expected, atol=1e-6)
        first_actions.append(expected)
    assert not np.allclose(first_actions[0], first_actions[1])


@pytest.mark.parametrize("format_", FORMATS)
def test_numeric_noncontiguous_ids(tmp_path, format_):
    # The repository fixture's ids are "0" and "3".
    Dataset(QPOS_FIXTURE).write(tmp_path, format=format_, fps=FPS, success_only=True)
    episodes = _load(tmp_path)["episodes"]
    assert [
        (e["episode_index"], e["source"]["index"], e["source"]["id"]) for e in episodes
    ] == [(0, 1, "3")]


def test_duplicate_source_ids_stay_distinguishable(tmp_path):
    # Two metadata entries naming the same episode directory: the source is
    # ambiguous, so both are recorded with their distinct metadata positions.
    source = _write_source(
        tmp_path / "source",
        episodes=[("3", "3", True, True, 0), ("3", "3", False, True, 0)],
    )
    Dataset(source).write(tmp_path / "out", format="lerobot_v2.1", fps=FPS)
    episodes = _load(tmp_path / "out")["episodes"]
    assert [
        (e["source"]["index"], e["source"]["id"], e["source"]["success"])
        for e in episodes
    ] == [
        (0, "3", True),
        (1, "3", False),
    ]


# --- Privacy and unknown fields ---------------------------------------------


@pytest.mark.parametrize("format_", FORMATS)
def test_sensitive_fields_withheld_by_default(export, format_):
    output = export(format_)
    provenance = _load(output)
    assert "operator" not in provenance["source"]
    assert "location" not in provenance["source"]
    assert provenance["withheld"] == ["location", "operator", "site_notes"]
    for name, text in _metadata_texts(output).items():
        for value in (OPERATOR, LOCATION, UNKNOWN_FIELD_VALUE):
            assert value not in text, f"{value!r} leaked into {name}"


@pytest.mark.parametrize("format_", FORMATS)
def test_sensitive_fields_opt_in(export, format_):
    provenance = _load(export(format_, include_sensitive_metadata=True))
    assert provenance["source"]["operator"] == OPERATOR
    assert provenance["source"]["location"] == LOCATION
    # Unknown fields are never copied: nothing says whether they are sensitive.
    assert "site_notes" not in provenance["source"]
    assert provenance["withheld"] == ["site_notes"]


def test_unknown_episode_and_task_fields_withheld(tmp_path):
    source = _write_source(tmp_path / "source")
    meta = yaml.safe_load((source / "metadata.yaml").read_text())
    meta["episodes"][0]["notes"] = "operator was tired"
    meta["tasks"][1]["owner"] = "someone"
    with open(source / "metadata.yaml", "w") as f:
        yaml.safe_dump(meta, f)
    Dataset(source).write(
        tmp_path / "out",
        format="lerobot_v2.1",
        fps=FPS,
        include_sensitive_metadata=True,
    )
    provenance = _load(tmp_path / "out")
    assert provenance["withheld"] == ["episodes[].notes", "site_notes", "tasks[].owner"]
    text = (tmp_path / "out" / "meta" / "openarm.json").read_text()
    assert "operator was tired" not in text
    assert "someone" not in text
    assert provenance["source"]["tasks"] == TASKS


def test_dataset_without_sensitive_fields(tmp_path):
    source = _write_source(tmp_path / "source")
    meta = yaml.safe_load((source / "metadata.yaml").read_text())
    for key in ("operator", "location", "site_notes"):
        del meta[key]
    with open(source / "metadata.yaml", "w") as f:
        yaml.safe_dump(meta, f)
    Dataset(source).write(
        tmp_path / "out",
        format="lerobot_v2.1",
        fps=FPS,
        include_sensitive_metadata=True,
    )
    provenance = _load(tmp_path / "out")
    assert provenance["withheld"] == []
    assert "operator" not in provenance["source"]
    assert "location" not in provenance["source"]


# --- Older formats: nothing is fabricated -----------------------------------


def test_missing_optional_fields_are_not_fabricated(tmp_path):
    # 0.1.0 records neither operation_type (Metadata defaults it to "teleop")
    # nor frequencies nor a leader.
    Dataset(FIXTURE_DIR / "dataset_0.1.0").write(
        tmp_path, format="lerobot_v2.1", fps=FPS
    )
    origin = _load(tmp_path)["source"]
    assert origin["version"] == "0.1.0"
    assert "operation_type" not in origin
    assert "frequencies" not in origin
    assert "leader" not in origin["equipment"]
    assert origin["equipment"]["id"] == "Test"


def test_unversioned_dataset(tmp_path):
    path = FIXTURE_DIR / "dataset_unversioned"
    Dataset(path).write(tmp_path, format="lerobot_v2.1", fps=FPS)
    provenance = _load(tmp_path)
    origin = provenance["source"]
    assert origin["version"] is None
    # The equipment as this package reads it, the same normalisation the
    # export itself is built from.
    assert origin["equipment"] == {
        "id": "Test",
        "version": "1.0",
        "embodiments": {"arms": {"id": "OpenArm", "version": "1.2"}},
        "perceptions": {
            "cameras": {"left_wrist": {}, "right_wrist": {}, "ceiling": {}, "head": {}}
        },
    }
    assert [e["source"]["id"] for e in provenance["episodes"]] == ["0", "3"]
    assert provenance["withheld"] == ["location", "operator"]


def test_yaml_dates_are_written_as_iso_strings(tmp_path):
    source = _write_source(tmp_path / "source")
    meta = yaml.safe_load((source / "metadata.yaml").read_text())
    meta["equipment"]["calibrated_on"] = datetime.date(2026, 1, 2)
    with open(source / "metadata.yaml", "w") as f:
        yaml.safe_dump(meta, f)
    Dataset(source).write(tmp_path / "out", format="lerobot_v2.1", fps=FPS)
    assert (
        _load(tmp_path / "out")["source"]["equipment"]["calibrated_on"] == "2026-01-02"
    )


@pytest.mark.parametrize("value", (b"\x00\x01", float("nan")))
def test_unrepresentable_metadata_fails_before_writing(tmp_path, value):
    source = _write_source(tmp_path / "source")
    meta = yaml.safe_load((source / "metadata.yaml").read_text())
    meta["equipment"]["blob"] = value
    with open(source / "metadata.yaml", "w") as f:
        yaml.safe_dump(meta, f)
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="equipment"):
        Dataset(source).write(output, format="lerobot_v2.1", fps=FPS)
    assert not output.exists() or not any(output.iterdir())


# --- Failures, determinism, immutability -----------------------------------


@pytest.mark.parametrize(
    "episodes, options",
    (
        ([], {}),
        ([("ep-0042", "0", False, True, 0)], {"success_only": True}),
        (EPISODES, {"fps": 0}),
    ),
)
@pytest.mark.parametrize("format_", FORMATS)
def test_failed_conversion_writes_no_provenance(tmp_path, format_, episodes, options):
    source = _write_source(tmp_path / "source", episodes=episodes)
    output = tmp_path / "out"
    options = {"fps": FPS, **options}
    with pytest.raises(ValueError):
        Dataset(source).write(output, format=format_, **options)
    assert not (output / "meta" / "openarm.json").exists()


@pytest.mark.parametrize("format_", FORMATS)
def test_provenance_is_deterministic(tmp_path, source, format_):
    for name in ("a", "b"):
        Dataset(source).write(tmp_path / name, format=format_, fps=FPS)
    first = (tmp_path / "a" / "meta" / "openarm.json").read_bytes()
    assert first == (tmp_path / "b" / "meta" / "openarm.json").read_bytes()


def test_source_metadata_is_not_mutated(tmp_path):
    source = _write_source(tmp_path / "source")
    raw = (source / "metadata.yaml").read_bytes()
    meta = Metadata(source / "metadata.yaml")
    before = copy.deepcopy(meta.data)
    Dataset(source, meta=meta).write(
        tmp_path / "out",
        format="lerobot_v2.1",
        fps=FPS,
        include_sensitive_metadata=True,
    )
    assert meta.data == before
    assert (source / "metadata.yaml").read_bytes() == raw


# --- The native layout is untouched -----------------------------------------

NATIVE_META_FILES = {
    "lerobot_v2.1": {
        "meta/episodes.jsonl",
        "meta/episodes_stats.jsonl",
        "meta/info.json",
        "meta/stats.json",
        "meta/tasks.jsonl",
    },
    "lerobot_v3.0": {
        "meta/episodes/chunk-000/file-000.parquet",
        "meta/info.json",
        "meta/stats.json",
        "meta/tasks.parquet",
    },
}
NATIVE_META_FILES["gr00t"] = NATIVE_META_FILES["lerobot_v2.1"] | {"meta/modality.json"}
DATA_COLUMNS = [
    "action",
    "observation.state",
    "timestamp",
    "frame_index",
    "episode_index",
    "index",
    "task_index",
    "success",
    "last_frame_index",
]


@pytest.mark.parametrize("format_", FORMATS)
def test_only_the_sidecar_is_added(export, format_):
    output = export(format_)
    written = {
        p.relative_to(output).as_posix()
        for p in (output / "meta").rglob("*")
        if p.is_file()
    }
    assert written == NATIVE_META_FILES[format_] | {"meta/openarm.json"}
    assert list(_exported_frames(output).columns) == DATA_COLUMNS
    with open(output / "meta" / "info.json") as f:
        info = json.load(f)
    assert "openarm" not in json.dumps(list(info))


# --- Reading provenance back ------------------------------------------------


def _tampered(export, tmp_path, edit):
    output = tmp_path / "tampered"
    shutil.copytree(export("lerobot_v2.1"), output)
    path = output / "meta" / "openarm.json"
    provenance = json.loads(path.read_text())
    edit(provenance)
    path.write_text(json.dumps(provenance))
    return output


def _swap_first_two(provenance):
    episodes = provenance["episodes"]
    episodes[0], episodes[1] = episodes[1], episodes[0]


def _duplicate_source_index(provenance):
    provenance["episodes"][1]["source"]["index"] = 0


def _drop_episode(provenance):
    provenance["episodes"].pop()


@pytest.mark.parametrize(
    "edit",
    (
        lambda p: p.update(schema_version=2),
        lambda p: p.pop("episodes"),
        lambda p: p.pop("source"),
        lambda p: p["episodes"][0]["source"].pop("id"),
        lambda p: p["episodes"][0].update(episode_index="0"),
        _swap_first_two,
        _duplicate_source_index,
        _drop_episode,
    ),
    ids=(
        "unknown-schema-version",
        "no-episodes",
        "no-source",
        "episode-without-source-id",
        "non-integer-index",
        "out-of-order",
        "duplicate-source-index",
        "count-differs-from-info",
    ),
)
def test_load_provenance_rejects_malformed(export, tmp_path, edit):
    with pytest.raises(ValueError):
        _load(_tampered(export, tmp_path, edit))


def test_load_provenance_rejects_invalid_json(export, tmp_path):
    output = tmp_path / "broken"
    shutil.copytree(export("lerobot_v2.1"), output)
    (output / "meta" / "openarm.json").write_text("{not json")
    with pytest.raises(ValueError):
        _load(output)


def test_load_provenance_without_sidecar(tmp_path):
    with pytest.raises(FileNotFoundError):
        _load(tmp_path)


# --- Downstream loaders -----------------------------------------------------


@pytest.mark.parametrize("format_", FORMATS)
def test_lerobot_loads_export_with_provenance(export, format_):
    lerobot = pytest.importorskip("lerobot")
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    reads_v30 = packaging.version.parse(lerobot.__version__) >= packaging.version.parse(
        "0.5.0"
    )
    if reads_v30 != (format_ == "lerobot_v3.0"):
        pytest.skip(f"lerobot {lerobot.__version__} does not read {format_}")
    output = export(format_, success_only=True)
    dataset = LeRobotDataset(repo_id="test/provenance", root=output)
    assert dataset.num_episodes == len(_load(output)["episodes"])
    assert dataset[0]["action"].shape[0] == 17


# --- CLI --------------------------------------------------------------------


@pytest.mark.parametrize("include", (False, True))
def test_cli_include_sensitive_metadata(tmp_path, monkeypatch, include):
    from openarm_dataset import convert

    argv = [
        "openarm-dataset-convert",
        str(QPOS_FIXTURE),
        str(tmp_path),
        "--format",
        "lerobot_v2.1",
    ]
    if include:
        argv.append("--include-sensitive-metadata")
    monkeypatch.setattr("sys.argv", argv)
    convert.main()
    origin = _load(tmp_path)["source"]
    assert ("operator" in origin) is include
    assert ("location" in origin) is include


@pytest.mark.parametrize("format_", ("openarm", "robot_eval_logger"))
def test_cli_include_sensitive_metadata_rejected_for_other_formats(
    tmp_path, monkeypatch, format_
):
    from openarm_dataset import convert

    monkeypatch.setattr(
        "sys.argv",
        [
            "openarm-dataset-convert",
            str(QPOS_FIXTURE),
            str(tmp_path / "out"),
            "--format",
            format_,
            "--include-sensitive-metadata",
        ],
    )
    with pytest.raises(SystemExit):
        convert.main()
