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

"""Survey which source metadata survives each training export (GH-71).

Builds a representative OpenArm 0.4.0 dataset from the repository fixture
(distinctive, non-contiguous episode ids, a teleoperation leader, operator,
location, an unknown custom field and ``valid`` flags), runs the real
exporters, then searches every file the export wrote under ``meta/`` plus the
data parquet schema for each distinctive source string.

Usage::

    python research/scripts/survey_exports.py OUT_DIR [FORMAT ...]

FORMAT is any of lerobot_v2.1, lerobot_v3.0, gr00t (default: all three).
Writes OUT_DIR/survey.json and prints a Markdown table.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys

import pandas as pd
import yaml

from openarm_dataset import Dataset

REPO = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixture" / "dataset_0.4.0_qpos"

# Source episodes, in metadata order: (new id, fixture episode, success, valid).
EPISODES = [
    ("ep-0042", "0", False, True),
    ("ep-0007", "3", True, False),
    ("ep-0100", "3", True, True),
]


def build_source(root: pathlib.Path) -> pathlib.Path:
    """Write the representative source dataset under ``root``."""
    meta = yaml.safe_load((FIXTURE / "metadata.yaml").read_text())
    meta["operator"] = "Operator-Alice-Survey"
    meta["location"] = "Lab-Room-B12-Survey"
    meta["site_notes"] = "Unknown-Custom-Field-Survey"
    meta["equipment"]["id"] = "OpenArm-Rig-7-Survey"
    meta["equipment"]["version"] = "2.3-survey"
    meta["equipment"]["leader"]["ker"]["firmware_version"] = "9.8.7-survey"
    meta["tasks"] = [
        {"prompt": "Pick the cube.", "description": "Task-Description-Survey"},
    ]
    meta["episodes"] = []
    for new_id, fixture_id, success, valid in EPISODES:
        shutil.copytree(FIXTURE / "episodes" / fixture_id, root / "episodes" / new_id)
        meta["episodes"].append(
            {"id": new_id, "success": success, "task_index": 0, "valid": valid}
        )
    with open(root / "metadata.yaml", "w") as f:
        yaml.safe_dump(meta, f)
    return root


def string_leaves(value, path=""):
    """Yield ``(path, value)`` for every string leaf of a YAML tree."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from string_leaves(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from string_leaves(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def export_texts(output: pathlib.Path) -> dict[str, str]:
    """Return ``{relative path: searchable text}`` for the export's metadata."""
    texts = {}
    for path in sorted((output / "meta").rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(output).as_posix()
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
            texts[rel] = df.reset_index().to_json(orient="records")
        else:
            texts[rel] = path.read_text(encoding="utf-8")
    for path in sorted((output / "data").rglob("*.parquet")):
        # Data parquet: the column names are the only metadata it carries.
        rel = path.relative_to(output).as_posix()
        texts[rel] = json.dumps(list(pd.read_parquet(path).columns))
    return texts


def survey(out_dir: pathlib.Path, formats: list[str]) -> dict:
    """Run every export and record where each source string appears."""
    source = build_source(out_dir / "source")
    meta = yaml.safe_load((source / "metadata.yaml").read_text())
    leaves = [
        (path, value)
        for path, value in string_leaves(meta)
        # Values that the export reproduces for unrelated reasons (camera
        # names become feature keys, joint-free ids) are kept, but numeric-ish
        # strings like "1.0" would match anything.
        if not value.replace(".", "").isdigit()
    ]
    result = {"source": str(source), "formats": {}}
    for fmt in formats:
        for options_name, options in (
            ("all", {}),
            ("success_only", {"success_only": True}),
            ("valid_only", {"valid_only": True}),
        ):
            output = out_dir / f"{fmt}-{options_name}"
            Dataset(source).write(output, format=fmt, fps=30, **options)
            texts = export_texts(output)
            found = {}
            for path, value in leaves:
                needle = json.dumps(value, ensure_ascii=False)
                found[path] = sorted(
                    rel for rel, text in texts.items() if needle in text
                )
            result["formats"][f"{fmt}/{options_name}"] = {
                "files": sorted(texts),
                "found": found,
            }
    return result


def main():
    """Entry point."""
    out_dir = pathlib.Path(sys.argv[1])
    formats = sys.argv[2:] or ["lerobot_v2.1", "lerobot_v3.0", "gr00t"]
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    result = survey(out_dir, formats)
    (out_dir / "survey.json").write_text(json.dumps(result, indent=2))
    keys = list(result["formats"])
    print("| source field | value | " + " | ".join(keys) + " |")
    print("|---|---|" + "---|" * len(keys))
    first = result["formats"][keys[0]]["found"]
    meta = yaml.safe_load((out_dir / "source" / "metadata.yaml").read_text())
    values = dict(string_leaves(meta))
    for path in first:
        cells = []
        for key in keys:
            where = result["formats"][key]["found"][path]
            cells.append(", ".join(where) if where else "**lost**")
        print(f"| `{path}` | `{values[path]}` | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
