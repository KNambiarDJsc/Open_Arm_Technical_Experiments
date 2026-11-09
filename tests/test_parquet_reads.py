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

"""Parquet files must be read by path, not through Python file objects (GH-45).

A parquet read through a Python file object (what ``pd.read_parquet`` does
for a local path) can abort the process with SIGABRT at interpreter exit,
after the work is done. That abort is a race and cannot be tested reliably,
so these tests check its precondition: every ``pyarrow.parquet.read_table``
call made while reading a dataset receives a path.
"""

import os
from pathlib import Path
import shutil

import pandas as pd
import pyarrow.parquet as pq
import pytest

from openarm_dataset import Dataset
from openarm_dataset.repair import repair_dataset

FIXTURE_DIR = Path(__file__).parent / "fixture"
FIXTURES = sorted(p.name for p in FIXTURE_DIR.iterdir() if p.is_dir())


@pytest.fixture
def read_sources(monkeypatch):
    """Record the source of every ``pyarrow.parquet.read_table`` call."""
    sources = []
    read_table = pq.read_table

    def spy(source, *args, **kwargs):
        sources.append(source)
        return read_table(source, *args, **kwargs)

    # pd.read_parquet looks the function up on the module at call time.
    monkeypatch.setattr(pq, "read_table", spy)
    return sources


def _assert_all_paths(sources):
    assert sources, "no parquet file was read"
    file_objects = [s for s in sources if not isinstance(s, (str, os.PathLike))]
    assert not file_objects, f"read through Python file objects: {file_objects[:3]}"


@pytest.mark.parametrize("fixture", FIXTURES)
def test_sample_reads_by_path(read_sources, fixture):
    dataset = Dataset(FIXTURE_DIR / fixture)
    for episode in dataset.meta.episodes:
        dataset.sample(30, episode=episode)
    _assert_all_paths(read_sources)


@pytest.mark.parametrize("fixture", ("dataset_unversioned", "dataset_0.1.0"))
def test_format_upgrade_reads_by_path(read_sources, tmp_path, fixture):
    # Writing an old dataset in the current format rewrites its parquet files.
    Dataset(FIXTURE_DIR / fixture).write(tmp_path / "out")
    _assert_all_paths(read_sources)


def test_repair_reads_by_path(read_sources, tmp_path):
    # In place on a copy: the output mode symlinks cameras, which Windows
    # allows only with the symlink privilege.
    dataset = tmp_path / "dataset"
    shutil.copytree(FIXTURE_DIR / "dataset_0.3.0", dataset)
    repair_dataset(dataset)
    _assert_all_paths(read_sources)


@pytest.mark.parametrize("fixture", FIXTURES)
def test_read_matches_pandas(fixture):
    # Reading by path gives exactly the frames pd.read_parquet gives.
    from openarm_dataset._parquet import read_parquet

    paths = sorted((FIXTURE_DIR / fixture).rglob("*.parquet"))
    assert paths
    for path in paths:
        pd.testing.assert_frame_equal(read_parquet(path), pd.read_parquet(path))


def test_read_accepts_str_and_path(tmp_path):
    from openarm_dataset._parquet import read_parquet

    path = tmp_path / "frame.parquet"
    expected = pd.DataFrame({"timestamp": [1, 2], "value": [[0.5], [1.5]]})
    expected.to_parquet(path)
    pd.testing.assert_frame_equal(read_parquet(path), expected)
    pd.testing.assert_frame_equal(read_parquet(str(path)), expected)
