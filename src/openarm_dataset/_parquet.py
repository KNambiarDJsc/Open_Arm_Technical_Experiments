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

"""Read parquet files without aborting the process at exit (GH-45)."""

import os

import pandas as pd
import pyarrow.parquet as pq


def read_parquet(path: str | os.PathLike) -> pd.DataFrame:
    """Read a local parquet file into a DataFrame.

    Use this instead of ``pd.read_parquet``. pandas opens a local path as a
    Python file object, so pyarrow's buffers hold Python objects. An Arrow
    I/O thread can drop the last of them after the interpreter has started
    to finalize; acquiring the GIL then exits the thread, and the forced
    unwind through a C++ destructor calls ``std::terminate``. The process
    aborts (SIGABRT, "terminate called without an active exception") after
    its work is done, sometimes losing buffered output. Reading by path
    lets pyarrow open the file natively, with no Python object involved.
    See apache/arrow#34314.
    """
    return pq.read_table(os.fspath(path)).to_pandas()
