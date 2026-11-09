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

"""Adjacent finding, not part of GH-71: v2.1/GR00T read episode 0 even if filtered.

``lerobot_v21._write_metadata`` samples ``dataset.meta.episodes[0]`` for the
camera shapes in ``info.json``, even when ``valid_only``/``success_only``
excluded that episode (``lerobot_v30._write_info_json`` uses the first
exported episode instead). If the excluded episode is invalid because a
camera is missing, the export crashes after the data and videos were
written. Present on upstream 3d291fe and unchanged by this branch.

Usage::

    python research/scripts/repro_v21_first_episode.py OUT_DIR
"""

import pathlib
import shutil
import sys

import yaml

from openarm_dataset import Dataset

REPO = pathlib.Path(__file__).resolve().parents[2]


def main():
    """Entry point."""
    out = pathlib.Path(sys.argv[1])
    if out.exists():
        shutil.rmtree(out)
    root = out / "source"
    shutil.copytree(REPO / "tests" / "fixture" / "dataset_0.4.0_qpos", root)
    shutil.rmtree(root / "episodes" / "0" / "cameras" / "ceiling")
    meta = yaml.safe_load((root / "metadata.yaml").read_text())
    meta["episodes"][0]["valid"] = False
    meta["episodes"][1]["valid"] = True
    (root / "metadata.yaml").write_text(yaml.safe_dump(meta))
    for fmt in ("lerobot_v2.1", "gr00t", "lerobot_v3.0"):
        try:
            Dataset(root).write(out / fmt, format=fmt, fps=30, valid_only=True)
            print(f"{fmt}: valid_only export OK")
        except Exception as e:  # noqa: BLE001
            print(f"{fmt}: valid_only export FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
