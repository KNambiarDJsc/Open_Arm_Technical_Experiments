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

"""Measure how often a command aborts at interpreter exit (GH-45).

Runs each case many times as a fresh Python process and records the exit
code, the stderr signature and whether the command finished its work
before exiting. A run that did its work but exited with SIGABRT is the
GH-45 failure.

Usage::

    python exit_abort_stress.py --runs 2000 --jobs 16 --out result.json CASE[@SRC]...

``CASE@SRC`` runs the case with ``PYTHONPATH=SRC`` so that an older
checkout of ``openarm_dataset`` can be measured against the installed one.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import os
import pathlib
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import pandas as pd
import pyarrow

REPO = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixture" / "dataset_0.3.0"
NAN_REL = pathlib.Path("episodes/0/obs/arms/left/state.parquet")
ABORT_MESSAGE = "terminate called without an active exception"
# Imported by every child through PYTHONPATH. An aborting process would
# otherwise write a core dump; under WSL2 each one is a ~1.3 GB file in the
# Windows temp directory. A non-dumpable process writes none, whatever the
# kernel's core_pattern, and the flag does not change how the process exits.
DUMP_GUARD = """
import ctypes, sys
if sys.platform == "linux":
    ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE, 0
"""

READ_ALL = """
import sys
{imports}
for path in sys.argv[1:]:
    {read}
"""
SAMPLE = """
import sys
from openarm_dataset import Dataset
dataset = Dataset(sys.argv[1])
for episode in dataset.meta.episodes:
    dataset.sample(30, episode=episode)
print("sampled")
"""


def _prepare(work: pathlib.Path) -> dict:
    """Create the shared, read-only inputs every run uses."""
    source = work / "source"
    shutil.copytree(FIXTURE, source)
    # One isolated NaN, so that repair rewrites a file.
    path = source / NAN_REL
    # Same injection as tests/test_repair.py: a NaN inside the qpos list.
    df = pd.read_parquet(path)
    values = df["qpos"].tolist()
    item = list(values[5])
    item[0] = float("nan")
    values[5] = item
    df["qpos"] = values
    df.to_parquet(path)
    parquet = sorted(str(p) for p in source.rglob("*.parquet"))
    guard = work / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(DUMP_GUARD)
    return {"source": str(source), "parquet": parquet, "guard": str(guard)}


def _command(case: str, inputs: dict, run_dir: pathlib.Path):
    """Return (argv, success_check) for one run of ``case``."""
    py = sys.executable
    if case == "pandas-read":
        code = READ_ALL.format(
            imports="import pandas as pd", read="pd.read_parquet(path)"
        )
        return [py, "-c", code, *inputs["parquet"]], None
    if case == "pyarrow-path-read":
        code = READ_ALL.format(
            imports="import pyarrow.parquet as pq",
            read="pq.read_table(path).to_pandas()",
        )
        return [py, "-c", code, *inputs["parquet"]], None
    if case == "sample":
        return [py, "-c", SAMPLE, inputs["source"]], lambda out: "sampled" in out
    if case == "repair-cli":
        output = run_dir / "out"
        return (
            [py, "-m", "openarm_dataset.repair", inputs["source"], "-o", str(output)],
            lambda out: "repaired 1 value(s)" in out,
        )
    if case == "convert-openarm-cli":
        output = run_dir / "out"
        return (
            [py, "-m", "openarm_dataset.convert", inputs["source"], str(output)],
            lambda out: (output / "metadata.yaml").exists(),
        )
    if case == "validate-cli":
        return (
            [py, "-m", "openarm_dataset.validate", inputs["source"]],
            None,
        )
    raise SystemExit(f"unknown case {case!r}")


def _classify(returncode: int, stderr: str) -> str:
    if returncode == 0:
        return "ok"
    if returncode == -signal.SIGABRT:
        return "SIGABRT: " + (
            "terminate without active exception" if ABORT_MESSAGE in stderr else "other"
        )
    if returncode < 0:
        return f"signal {-returncode}"
    return f"exit {returncode}"


def _run_once(case, src, inputs, scratch, index):
    run_dir = pathlib.Path(tempfile.mkdtemp(dir=scratch, prefix=f"{index}-"))
    argv, check = _command(case, inputs, run_dir)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (inputs["guard"], src) if p)
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, env=env, timeout=300
        )
        outcome = _classify(result.returncode, result.stderr)
        did_work = None if check is None else bool(check(result.stdout))
        stderr_tail = result.stderr.strip().splitlines()[-1:] if outcome != "ok" else []
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
    return outcome, did_work, stderr_tail


def measure(case, src, inputs, scratch, runs, jobs) -> dict:
    """Run ``case`` ``runs`` times with ``jobs`` concurrent processes."""
    outcomes = collections.Counter()
    worked_then_failed = 0
    examples = collections.Counter()
    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        futures = [
            pool.submit(_run_once, case, src, inputs, scratch, i) for i in range(runs)
        ]
        for future in concurrent.futures.as_completed(futures):
            outcome, did_work, tail = future.result()
            outcomes[outcome] += 1
            if outcome != "ok" and did_work:
                worked_then_failed += 1
            for line in tail:
                examples[line[:160]] += 1
    failures = runs - outcomes["ok"]
    return {
        "case": case,
        "code": src or "installed",
        "runs": runs,
        "jobs": jobs,
        "seconds": round(time.monotonic() - start, 1),
        "outcomes": dict(outcomes),
        "failure_rate": failures / runs,
        "failed_after_finishing_work": worked_then_failed,
        "stderr_last_lines": dict(examples.most_common(3)),
    }


def main():
    """Entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("cases", nargs="+")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gh45-") as tmp:
        work = pathlib.Path(tmp)
        inputs = _prepare(work)
        scratch = work / "runs"
        scratch.mkdir()
        results = []
        for spec in args.cases:
            case, _, src = spec.partition("@")
            result = measure(case, src or None, inputs, scratch, args.runs, args.jobs)
            results.append(result)
            _save(args.out, results)
            print(json.dumps(result), flush=True)


def _save(out: pathlib.Path, results: list) -> None:
    environment = {
        "python": sys.version.split()[0],
        "pyarrow": pyarrow.__version__,
        "pandas": pd.__version__,
        "platform": platform.platform(),
        "cpus": os.cpu_count(),
    }
    out.write_text(
        json.dumps({"environment": environment, "results": results}, indent=2)
    )


if __name__ == "__main__":
    main()
