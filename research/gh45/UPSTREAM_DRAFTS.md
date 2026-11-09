# Upstream drafts for GH-45 (not posted)

Nothing below has been posted. Post only with the applicant's explicit
approval. A PR would contain `src/openarm_dataset/_parquet.py`, the
`dataset.py`/`repair.py` changes and `tests/test_parquet_reads.py`, not
`research/`.

Recommended order: post A first. It is useful on its own (it lets the
maintainers close #45 with evidence) and asks whether they want B.

---

## A. Issue comment on #45

> I measured this, in case it helps close it.
>
> **Cause:** apache/arrow#34314. `pd.read_parquet` opens a local path as a
> Python file object, so pyarrow's buffers hold Python objects. If an
> Arrow thread releases the last one after interpreter finalization has
> started, CPython exits that thread with `pthread_exit`. glibc's forced
> unwind then reaches a `noexcept` C++ destructor, and `std::terminate`
> aborts the process. That happens after the work is done.
>
> **The `repair.py` change in #73 fixes this test.** On Linux, with
> Python 3.12, pyarrow 26.0.1 and 16 processes in parallel, 2000 runs of
> `openarm-dataset-repair -o`:
> - with that one line reverted to `pd.read_parquet`: 79 SIGABRTs, the
>   same stderr as CI;
> - on `main`: 0.
>
> I also tried pyarrow on a Python file object without pandas: 139/2000.
> The same read by path: 0/2000. With `pre_buffer=False`: 62/2000, so
> that is not a fix.
>
> **The same pattern remains in `Dataset`.** `load_embodiment_value()`
> (used by `sample()`) and the format upgrade in `_write_embodiment_data()`
> still use `pd.read_parquet`. A script that samples the fixture and exits
> aborted 20/2000 times on `main`. I did *not* see it in the convert CLIs
> themselves (0/2000 for `--format lerobot_v2.1` and for the format
> upgrade), presumably because they do other work after the last read. So
> it is a hardening change for library users, not a fix for an observed
> CLI failure.
>
> If you'd like, I can send a small PR: one helper that reads by path, used
> at those three sites, plus a deterministic test that every `read_table`
> call receives a path. On `main` that test fails for `sample()` on every
> fixture version.

## B. PR description (only if A gets a yes)

**Title:** Read parquet by path in Dataset as well

Fix GH-45

`pd.read_parquet` opens a local path as a Python file object. pyarrow can
then release a Python-backed buffer on an Arrow thread after interpreter
finalization has started, which aborts the process with SIGABRT after its
work is done (apache/arrow#34314). #73 avoided this in `repair.py`;
`Dataset.load_embodiment_value()` and `Dataset._write_embodiment_data()`
still read through pandas.

This adds `openarm_dataset._parquet.read_parquet()`, which reads by path
through pyarrow, and uses it at all four sites. It returns the same
frames as `pd.read_parquet` (tested on every fixture version).

`tests/test_parquet_reads.py` checks the precondition deterministically:
every `pyarrow.parquet.read_table` call made while sampling, upgrading or
repairing a dataset receives a path. It fails on `main` and passes here.

Measured on Linux (Python 3.12, pandas 2.3.3, pyarrow 26.0.1, 2000 runs,
16 in parallel): a script that samples the fixture and exits aborted 20
times on `main` and 0 times with this change. The repair and convert CLIs
were 0 on both.

Full suite on Linux: 308 passed, 5 skipped (same skips as `main`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
