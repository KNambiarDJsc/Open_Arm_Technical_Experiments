# Loader tolerance probe

Command: `python research/scripts/probe_loader_tolerance.py OUT FORMAT`, run on
upstream `3d291fe` (no provenance changes) on 2026-11-08.

- LeRobot v2.1: Windows 11, Python 3.12.11, lerobot 0.3.3, torch 2.7.1.
- LeRobot v3.0: WSL2 Ubuntu, Python 3.12.3, lerobot 0.7.0, torch 2.15.0+cpu.

"loads" = `LeRobotDataset(repo_id=..., root=...)` succeeds; "frame 0" =
`ds[0]` succeeds (decodes video); "visible" = the extension can be read back
through the loader's API (`ds.meta.info`, `ds.meta.episodes`, `ds[0]`).

lerobot 0.3.3, format lerobot_v2.1

| extension | loads | frame 0 | visible via loader API |
|---|---|---|---|
| baseline | yes | yes | n/a |
| info.json extra top-level key | yes | yes | yes |
| extra per-episode field | yes | yes | yes |
| meta/openarm.json sidecar | yes | yes | n/a |
| extra data parquet column (not in info features) | yes | yes | yes |

lerobot 0.7.0, format lerobot_v3.0

| extension | loads | frame 0 | visible via loader API |
|---|---|---|---|
| baseline | yes | yes | n/a |
| info.json extra top-level key | yes | yes | no |
| extra per-episode field | yes | yes | yes |
| meta/openarm.json sidecar | yes | yes | n/a |
| extra data parquet column (not in info features) | no: DatasetGenerationError: An error occurred while generating the dataset | - | - |

Isaac-GR00T's own loader was not installed or tested.
