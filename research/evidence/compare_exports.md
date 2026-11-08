# Export files before and after the change

`research/scripts/compare_exports.py`: the survey's representative dataset
exported with upstream `3d291fe` (via `PYTHONPATH=<worktree>/src`) and with
commit `bc34001`, every file compared by SHA-256. Includes data parquet,
MP4 videos and every metadata file.

## LeRobot v2.1 and GR00T (Windows 11, lerobot 0.3.3, ffmpeg n9.0.2 from imageio-ffmpeg)

| export | unchanged files | added | changed/removed | result |
|---|---|---|---|---|
| gr00t-all | 24 identical | added: meta/openarm.json | changed/removed: - | OK |
| gr00t-success_and_valid_only | 12 identical | added: meta/openarm.json | changed/removed: - | OK |
| gr00t-success_only | 18 identical | added: meta/openarm.json | changed/removed: - | OK |
| gr00t-valid_only | 18 identical | added: meta/openarm.json | changed/removed: - | OK |
| lerobot_v2.1-all | 23 identical | added: meta/openarm.json | changed/removed: - | OK |
| lerobot_v2.1-success_and_valid_only | 11 identical | added: meta/openarm.json | changed/removed: - | OK |
| lerobot_v2.1-success_only | 17 identical | added: meta/openarm.json | changed/removed: - | OK |
| lerobot_v2.1-valid_only | 17 identical | added: meta/openarm.json | changed/removed: - | OK |

## LeRobot v3.0 (WSL2 Ubuntu, lerobot 0.7.0)

| export | unchanged files | added | changed/removed | result |
|---|---|---|---|---|
| lerobot_v3.0-all | 10 identical | added: meta/openarm.json | changed/removed: - | OK |
| lerobot_v3.0-success_and_valid_only | 10 identical | added: meta/openarm.json | changed/removed: - | OK |
| lerobot_v3.0-success_only | 10 identical | added: meta/openarm.json | changed/removed: - | OK |
| lerobot_v3.0-valid_only | 10 identical | added: meta/openarm.json | changed/removed: - | OK |
