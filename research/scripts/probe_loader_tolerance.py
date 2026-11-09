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

"""Probe which metadata extensions the installed LeRobot loader tolerates.

For the provenance design (GH-71): exports the 0.3.0 fixture with the
installed code, applies one candidate extension at a time to a copy, and
reports whether ``LeRobotDataset`` still loads it, reads frame 0, and
whether the extension is visible through the loader's API.

Usage::

    python research/scripts/probe_loader_tolerance.py OUT_DIR FORMAT

FORMAT is lerobot_v2.1 (run with lerobot 0.3.3) or lerobot_v3.0 (lerobot
>= 0.5).
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import traceback

import pandas as pd

import lerobot
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from openarm_dataset import Dataset

REPO = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixture" / "dataset_0.3.0"


def _extend_info(root: pathlib.Path):
    path = root / "meta" / "info.json"
    info = json.loads(path.read_text())
    info["openarm"] = {"equipment": {"id": "Test", "version": "1.0"}}
    path.write_text(json.dumps(info, indent=4))
    return lambda ds: "openarm" in ds.meta.info


def _extend_episodes(root: pathlib.Path):
    jsonl = root / "meta" / "episodes.jsonl"
    if jsonl.exists():
        rows = [json.loads(line) for line in jsonl.read_text().splitlines()]
        for row in rows:
            row["openarm_source_id"] = f"src-{row['episode_index']}"
        jsonl.write_text("".join(json.dumps(r) + "\n" for r in rows))
    else:
        path = root / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
        df = pd.read_parquet(path)
        df["openarm_source_id"] = [f"src-{i}" for i in df["episode_index"]]
        df.to_parquet(path, index=False)

    def visible(ds):
        episodes = ds.meta.episodes
        first = episodes[0] if not hasattr(episodes, "column_names") else None
        if first is not None:
            return "openarm_source_id" in first
        return "openarm_source_id" in episodes.column_names

    return visible


def _sidecar(root: pathlib.Path):
    (root / "meta" / "openarm.json").write_text(json.dumps({"schema_version": 1}))
    return lambda ds: None


def _extend_data(root: pathlib.Path):
    for path in (root / "data").rglob("*.parquet"):
        df = pd.read_parquet(path)
        df["openarm_source_id"] = "src"
        df.to_parquet(path, index=False)
    return lambda ds: "openarm_source_id" in ds[0]


PROBES = {
    "baseline": lambda root: (lambda ds: None),
    "info.json extra top-level key": _extend_info,
    "extra per-episode field": _extend_episodes,
    "meta/openarm.json sidecar": _sidecar,
    "extra data parquet column (not in info features)": _extend_data,
}


def main():
    """Entry point."""
    out_dir = pathlib.Path(sys.argv[1])
    fmt = sys.argv[2]
    if out_dir.exists():
        shutil.rmtree(out_dir)
    base = out_dir / "base"
    Dataset(FIXTURE).write(base, format=fmt, fps=30)
    print(f"lerobot {lerobot.__version__}, format {fmt}")
    print("| extension | loads | frame 0 | visible via loader API |")
    print("|---|---|---|---|")
    for name, apply in PROBES.items():
        root = out_dir / name.replace(" ", "_").replace("/", "_")
        shutil.copytree(base, root)
        visible = apply(root)
        try:
            ds = LeRobotDataset(repo_id="probe/openarm", root=root)
            loads = "yes"
            try:
                ds[0]
                frame = "yes"
            except Exception as e:  # noqa: BLE001
                frame = f"no: {type(e).__name__}: {str(e)[:80]}"
            seen = visible(ds)
            seen = "n/a" if seen is None else ("yes" if seen else "no")
        except Exception as e:  # noqa: BLE001
            loads = f"no: {type(e).__name__}: {str(e)[:100]}"
            frame = seen = "-"
            traceback.print_exc(limit=1, file=sys.stderr)
        print(f"| {name} | {loads} | {frame} | {seen} |")


if __name__ == "__main__":
    main()
