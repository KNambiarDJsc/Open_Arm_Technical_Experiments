# The Process That Finished Its Work and Then Crashed: Measuring a Shutdown Race in a Robot Dataset Toolkit

*An investigation of
[enactic/openarm_dataset#45](https://github.com/enactic/openarm_dataset/issues/45),
"Flaky test: tests/test_repair.py", on upstream revision `3d291fe`
(2026-11-04). Every number below comes from scripts and logs in
`research/` on the local branch `research/gh45-exit-abort`. Nothing was
pushed or posted upstream.*

## 1. The symptom

`openarm_dataset` is the toolkit Enactic uses to validate, repair and
convert OpenArm robot recordings into training formats (LeRobot, GR00T,
Rerun). Since June 2026 its CI has occasionally failed in one place:

```
>       assert result.returncode == 0
E       AssertionError: assert -6 == 0
E        +  where -6 = CompletedProcess(..., stdout='episodes/0/obs/arms/left/state.parquet:
            repaired 1 value(s)\n', stderr='terminate called without an active exception\n')
```

The test runs `openarm-dataset-repair` as a subprocess. Three details in
that one line carry the whole investigation:

- **`-6`** is a negative return code: the process did not exit, it was
  killed by signal 6, `SIGABRT`.
- **`stdout`** says `repaired 1 value(s)`. The repair had finished.
- **`stderr`** says `terminate called without an active exception`, the
  message the GNU C++ runtime prints when `std::terminate()` is called
  outside exception handling.

A Python program did its job and then died in C++ code on the way out.

## 2. Why a flaky test deserves this much attention

A flaky test is usually treated as a test problem. This one is a product
problem that a test happened to notice:

- The CLIs are meant to be scripted. A batch job with `set -e`, a Makefile
  or an orchestrator that checks exit codes sees a failure for work that
  succeeded, and may retry, alert or throw the output away.
- `SIGABRT` kills the process before Python flushes its buffered output.
  In 6 of the 99 aborted runs below that had a success check, the
  program's final output never reached the pipe.
- Every abort writes a core dump if the system allows it. Under WSL2 each
  was a 1.3 GB file in the Windows temp folder, and the first ten filled a
  disk during this investigation.
- Re-running CI hides it. The run cited in the issue failed on attempt 1
  and passed on attempt 2, so its recorded conclusion is "success". In
  242 CI runs since May, three more aborts are visible, all in the two
  repair CLI tests.

## 3. What had already been done

The issue's only comment links
[apache/arrow#34314](https://github.com/apache/arrow/issues/34314), an open
Arrow issue with the same message. On 2026-09-29 a workaround landed in
`repair.py` as part of an unrelated PR (#73, the `robot_eval_logger`
exporter), 30 minutes after that PR's own CI hit the abort:

```python
# Read by path, not through pandas: pd.read_parquet opens local files as Python
# file objects, and pyarrow can still be releasing one on a worker thread when
# the interpreter exits, which aborts the process.
df = pq.read_table(path).to_pandas()
```

The issue stayed open. Nobody had measured whether the workaround works,
whether its explanation is right, or whether the same pattern exists
elsewhere, and CI could not tell: 136 runs before the workaround, 17
after. For a flake seen in roughly one run in fifty, 17 clean runs are
expected even if nothing changed.

## 4. Mechanism

The Arrow issue includes a core-dump backtrace. Read bottom-up (frames
abridged):

```
#26 arrow::MergedGenerator<...>::State::_M_dispose      an Arrow thread drops the reader
#22 parquet::ParquetFileReader::~ParquetFileReader
#20 arrow::io::internal::ReadRangeCache::Impl::~Impl    pre-buffered ranges released
#15 arrow::py::PyBuffer::~PyBuffer                       buffer backed by a Python object
#14 PyGILState_Ensure                                    needs the GIL to drop that object
#11 PyThread_exit_thread                                 interpreter is finalizing: exit thread
#10 __pthread_exit → _Unwind_ForcedUnwind                glibc unwinds the C++ stack
#4  std::terminate                                       unwinding met a noexcept destructor
#0  raise(SIGABRT)
```

1. **pandas opens the file itself.** For a local path, `pd.read_parquet`
   calls `open()` and hands pyarrow a Python file object
   (`pandas/io/parquet.py:141` → `pandas/io/common.py:882` in pandas
   2.3.3; a traceback during this work showed exactly that call).
2. **pyarrow wraps it.** Data read through a Python file object lives in
   `PyBuffer`s, C++ buffers holding a reference to a Python object.
   Releasing one needs the GIL.
3. **The release can happen on an Arrow thread**, not on the thread that
   called `read_parquet`, because pyarrow reads asynchronously on its own
   thread pool.
4. **If that happens after Python has begun finalizing**, the Arrow
   thread's attempt to take the GIL makes CPython (before 3.14) call
   `PyThread_exit_thread()`.
5. **glibc implements `pthread_exit` with a forced unwind** that runs C++
   destructors. Destructors are `noexcept` by default since C++11, and
   unwinding through a `noexcept` frame calls `std::terminate()`.

CPython's documentation now says so directly: on POSIX
`PyThread_exit_thread` "may unwind the stack and run C++ destructors… If a
`noexcept` function is reached, the process may terminate". Two
predictions follow, examined in section 7.4:

- **Windows** ends the thread with `_endthreadex()`, which runs no C++
  destructors: no abort.
- **Python 3.14** changed `PyGILState_Ensure`, `PyEval_RestoreThread` and
  `PyEval_AcquireThread` to "hang the current thread, rather than
  terminating it" during finalization: no abort.

If pyarrow opens the file from a path instead, buffers are native memory,
releasing them needs no GIL, and step 4 cannot happen.

## 5. One door closed, three still open

A search for every parquet read in the package:

| site | used by | how it reads |
|---|---|---|
| `repair._repair_parquet` | `openarm-dataset-repair` | by path (since #73) |
| `validator.py`, 3 sites | `openarm-dataset-validate` | by path |
| `Dataset.load_embodiment_value` (`dataset.py:659`) | `Dataset.sample()`, hence every LeRobot, GR00T, rrd and robot_eval_logger conversion | **pandas** |
| `Dataset._write_embodiment_data` (`dataset.py:801, 812`) | writing an unversioned or 0.1.0 dataset in the current format | **pandas** |

The test suite could not see these. The conversion tests call
`convert.main()` inside the pytest process, so the interpreter never exits
after a conversion. Only `repair` and `validate` ever ran as real
subprocesses, and `validate` already read by path.

My hypothesis at this point was that every conversion CLI could abort the
same way. Section 7 shows that this was half right.

## 6. Method

A flake seen once in dozens of CI runs needs a different instrument from
a unit test. `research/scripts/exit_abort_stress.py` runs one command
thousands of times, each a fresh Python process, 16 at a time, and records
for each run:

- the exit status (`ok`, `SIGABRT` with or without the terminate message,
  other signals, non-zero exits), and the last stderr line;
- whether the command had finished its real work (output file written, or
  the expected line on stdout).

Cases run one after another so that the load is comparable. Code variants
are selected with `PYTHONPATH`, and the runner prints which
`openarm_dataset` each variant imports and whether it contains
`pd.read_parquet`:

- **main**: upstream `3d291fe`, unchanged;
- **revert-repair**: `main` with only the workaround line put back to
  `pd.read_parquet`, a one-line ablation;
- **fix**: this branch (section 8).

Every abort produces a core dump, and WSL2 ignores `ulimit -c 0` because
the kernel hands cores to a pipe. The harness therefore puts a
`sitecustomize.py` on each child's `PYTHONPATH` that calls
`prctl(PR_SET_DUMPABLE, 0)`. A non-dumpable process writes no core under
any `core_pattern`; it still dies by `SIGABRT` (verified with a
deliberate `os.abort()`).

Environment: WSL2 Ubuntu 24.04 (glibc 2.39), 16 logical CPUs, Python
3.12.3 (CI uses 3.12), pandas 2.3.3, pyarrow 26.0.1 (newest release; CI
hit the abort with 25.0.1). Inputs: the repository's `dataset_0.3.0`
fixture with one injected NaN, the same injection `test_repair.py` uses.

## 7. Results

2000 runs per case, 16 concurrent processes
(`research/gh45/evidence/stress_linux_py312.json`). "Finished" counts
aborted runs whose work was complete before the abort.

### 7.1 What triggers it

| read | aborts |
|---|---|
| `pd.read_parquet(path)` | 120 / 2000 (6.0%) |
| `pq.read_table(open(path, "rb"))`, no pandas | 139 / 2000 (7.0%) |
| `pd.read_parquet(path, pre_buffer=False)` | 62 / 2000 (3.1%) |
| `pq.read_table(path)` | **0 / 2000** |

pandas is not the cause; the Python file object is. pyarrow reading the
same file object without pandas aborts as often. Turning off
pre-buffering halves the rate but does not remove it, so it is not a fix.
Reading by path removes it completely under the same load.

### 7.2 Did the September workaround fix the flaky test?

| repair CLI | aborts | finished first |
|---|---|---|
| workaround reverted (one line) | 79 / 2000 (4.0%) | 76 |
| `main` (workaround in) | **0 / 2000** | – |
| fix | **0 / 2000** | – |

Yes. Putting back the single line reproduces the CI failure at 4%, with
the same stderr message; 76 of the 79 runs had printed `repaired 1
value(s)`, and in the other three the abort ate that line. With the
workaround: 0 in 2000, a 95% upper bound of 0.15% (rule of three). Issue
#45, as filed, is fixed on `main`.

### 7.3 The other doors

| case | `main` | fix |
|---|---|---|
| `Dataset.sample()` over every episode, then exit | **20 / 2000 (1.0%)**, 17 finished | **0 / 2000** |
| `openarm-dataset-convert --format lerobot_v2.1` | 0 / 2000 | 0 / 2000 |
| `openarm-dataset-convert` of an unversioned dataset (format upgrade) | 0 / 2000 | 0 / 2000 |

The library path aborts: a program that samples a dataset and exits
crashes in 1% of runs on `main` and never with the fix. But the two
shipped conversion CLIs did not abort in 2000 runs each, even on `main`.

That falsifies the stronger form of my hypothesis, and the reason is
instructive. The race needs an Arrow thread to release a Python-backed
buffer *while the interpreter is finalizing*. In the `sample` case the
last read is moments before exit. The convert CLIs keep working after
their last read (encoding video, writing parquet and metadata), so by
the time Python shuts down, Arrow has long since released everything. The
same unsafe read is harmless or dangerous depending on how close it sits
to the end of the process.

So the honest summary of exposure on `main` is:

- the shipped CLIs: no abort observed (each < 0.15% at 95% confidence on
  this workload);
- any code that reads recordings through `Dataset` and exits soon after
  (an analysis script, a quick inspection, a pipeline step that samples
  one episode): about 1% of runs under load, on Linux, Python < 3.14.

### 7.4 Python version: a preliminary twist

Section 4 predicted that Python 3.14, which hangs rather than exits a
thread that wants the GIL during finalization, would not abort. The
experiment was cut short, so this part is preliminary
(`evidence/hangs_py313_py314.txt`):

- **Build does not matter on 3.12.** uv's python-build-standalone 3.12.14
  aborts like Ubuntu's 3.12.3: 47 vs 41 per 1000 for `pd.read_parquet`,
  0 and 0 for reading by path.
- **On 3.13.15 and 3.14.7 a run hung instead.** In each, one child never
  exited (killed after 300 s; normal runs take about 2 s), and the run
  stopped at that first hang, so no rate was recorded.

A hang at exit is consistent with the 3.14 documentation ("will infinitely
hang the thread, which may cause deadlocks"): if anything waits for that
Arrow thread during shutdown, the process never ends. That 3.13 hangs too
is not explained by the 3.14 change and was not investigated further. If
it holds up, upgrading Python does not remove this bug. It turns a crash
into a CI job that runs until its timeout, which is worse. Reading by path
avoids the trigger on every version.

The Windows prediction (`_endthreadex` runs no destructors, so no abort)
was not tested.

## 8. The fix

```python
def read_parquet(path: str | os.PathLike) -> pd.DataFrame:
    return pq.read_table(os.fspath(path)).to_pandas()
```

One private helper, `openarm_dataset._parquet.read_parquet`, now used at
all four sites, with the mechanism in its docstring so that the next
person does not have to rediscover it. Three source files change.

**Is it a drop-in replacement?** `pd.read_parquet` with the pyarrow engine
is `read_table(..., use_pandas_metadata=True)` followed by `to_pandas()`
and restoring `df.attrs`. When all columns are read, `to_pandas()`
rebuilds the same index from the same pandas metadata, and these files
carry no `attrs`. Two checks back that up: a test compares both readers
on every parquet file of every fixture version, and the whole suite
passes (section 9).

**How do you regression-test a race?** Not by running it until it fails;
that test would itself be flaky. `tests/test_parquet_reads.py` tests the
precondition. It wraps `pyarrow.parquet.read_table`, which
`pd.read_parquet` also calls, and asserts that every call made while
sampling, upgrading or repairing a dataset receives a path. On `main` it
fails for `Dataset.sample()` on all six fixture versions and for the
format upgrade, listing the `_io.BufferedReader` objects it caught. With
the fix it passes, deterministically, in about two seconds, and it will
catch anyone who reintroduces `pd.read_parquet`.

Results: 16 new tests, 15 failing before and all passing after (the one
that passes before is the repair guard, which `main` already satisfies).
Full suite on Linux with the fix: 308 passed, 5 skipped, the same skips
as `main` (missing optional extras and `ffprobe`).

## 9. Compatibility

- **Same frames.** `test_read_matches_pandas` compares the new reader with
  `pd.read_parquet` on every parquet file of all six fixture versions
  (0.1.0 through 0.4.0, and unversioned): identical, including dtypes and
  index.
- **Same behaviour.** The full suite passes on Linux with the fix (308
  passed, 5 skipped, the same skips as `main`). The repair, sample and
  convert stress cases produced their outputs in all 8,000 fixed-code
  runs.
- **No API change.** The helper is private, and no public signature
  changes.
- **Not done:** a byte-for-byte comparison of converted outputs before and
  after. `research/scripts/compare_exports.py` is on the branch for it,
  but it was not run.
## 10. Limitations

- Measured on WSL2: Linux with a real glibc, but not a GitHub Actions
  runner. The CI evidence (four aborts, same message, same tests) agrees
  with it.
- Rates depend on load. These are 16 processes on 16 CPUs; on a quiet
  machine the absolute numbers are lower. Comparisons between variants
  under the same load are what the experiment supports.
- "0 / 2000" means "below about 0.15% at 95% confidence on this workload",
  not "impossible". A longer recording, a different machine or a
  different exit path could change the convert CLIs' exposure.
- The root cause lives between pyarrow and CPython. This change removes
  the trigger inside this package; `pd.read_parquet` in user code on
  Linux with Python < 3.14 can still abort.
- `merge.py` and `upload.py` read no parquet and were not measured.

## 11. Takeaways

- **Read the failure line literally.** A negative return code, a stdout
  that shows success and a C++ runtime message on stderr together say
  "crash during shutdown, after the work". That framed every later step.
- **Ablate one line.** Reverting only the workaround turned "the flake
  hasn't recurred" into 79 aborts versus 0, and settled whether the
  existing fix works.
- **A flaky test can be the only window onto a wider bug**, but measure
  before claiming it. The unsafe pattern was in three more places. The
  library path did abort; the CLIs did not, and the reason (distance
  between the last read and process exit) is the most useful thing the
  experiment taught.
- **Test the precondition, not the race.** A deterministic check that no
  read goes through a file object guards the fix better than a stress
  test in CI ever could.
- **Instrument your instrument.** The first pilot filled a disk with core
  dumps. Making children non-dumpable let 26,000 runs, 420 of
  them aborting, finish without writing a single core file.
