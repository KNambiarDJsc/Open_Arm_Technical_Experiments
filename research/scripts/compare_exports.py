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

"""Check that the provenance change leaves every other export file unchanged.

Two steps, run once with the upstream code and once with the change::

    PYTHONPATH=<upstream checkout>/src python compare_exports.py export OUT_A FORMAT...
    python compare_exports.py export OUT_B FORMAT...
    python compare_exports.py compare OUT_A OUT_B

``export`` writes the representative dataset of ``survey_exports.py`` in
every FORMAT under four episode selections. ``compare`` reports, for every
file in either tree, whether the bytes are identical; ``meta/openarm.json``
is expected only in OUT_B.
"""

from __future__ import annotations

import hashlib
import pathlib
import shutil
import sys

import openarm_dataset
from openarm_dataset import Dataset

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from survey_exports import build_source  # noqa: E402

SELECTIONS = {
    "all": {},
    "success_only": {"success_only": True},
    "valid_only": {"valid_only": True},
    "success_and_valid_only": {"success_only": True, "valid_only": True},
}


def export(out_dir: pathlib.Path, formats: list[str]) -> None:
    """Export the representative dataset under every selection."""
    print(f"openarm_dataset from {pathlib.Path(openarm_dataset.__file__).parent}")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    source = build_source(out_dir / "source")
    for fmt in formats:
        for name, options in SELECTIONS.items():
            Dataset(source).write(
                out_dir / f"{fmt}-{name}", format=fmt, fps=30, **options
            )


def _digests(root: pathlib.Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def compare(a: pathlib.Path, b: pathlib.Path) -> int:
    """Print a per-export summary; return the number of unexpected differences."""
    problems = 0
    for export_a in sorted(p for p in a.iterdir() if p.is_dir() and p.name != "source"):
        export_b = b / export_a.name
        da, db = _digests(export_a), _digests(export_b)
        added = sorted(set(db) - set(da))
        removed = sorted(set(da) - set(db))
        changed = sorted(k for k in set(da) & set(db) if da[k] != db[k])
        same = len(set(da) & set(db)) - len(changed)
        unexpected = [f for f in added if f != "meta/openarm.json"] + removed + changed
        problems += len(unexpected)
        status = "OK" if not unexpected else "DIFFERS"
        print(
            f"| {export_a.name} | {same} identical | added: {', '.join(added) or '-'}"
            f" | changed/removed: {', '.join(changed + removed) or '-'} | {status} |"
        )
    return problems


def main():
    """Entry point."""
    command = sys.argv[1]
    if command == "export":
        export(pathlib.Path(sys.argv[2]), sys.argv[3:])
    elif command == "compare":
        print("| export | unchanged files | added | changed/removed | result |")
        print("|---|---|---|---|---|")
        sys.exit(
            1 if compare(pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])) else 0
        )
    else:
        raise SystemExit(f"unknown command {command!r}")


if __name__ == "__main__":
    main()
