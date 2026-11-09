# Baseline field survey (upstream 3d291fe)

`python research/scripts/survey_exports.py OUT FORMAT...` on unmodified upstream code, 2026-11-08. A cell names the files under the export where the source string appears (meta/ files, plus the data parquet column names); **lost** means it appears nowhere. Numeric-looking strings (versions such as "0.4.0") are excluded from the search because they match unrelated numbers; they are also lost (see PROVENANCE_DESIGN.md section 1).

## LeRobot v2.1 and GR00T (Windows 11, Python 3.12.11, lerobot 0.3.3)

| source field | lerobot_v2.1/all | lerobot_v2.1/success_only | lerobot_v2.1/valid_only | gr00t/all | gr00t/success_only | gr00t/valid_only |
|---|---|---|---|---|---|---|
| `episodes[0].id` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `episodes[1].id` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `episodes[2].id` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `equipment.embodiments.arms.id` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `equipment.embodiments.lifter.home` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `equipment.embodiments.lifter.id` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `equipment.embodiments.lifter.mechanism` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `equipment.embodiments.lifter.unit` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `equipment.id` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `equipment.leader.ker.firmware_version` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `equipment.leader.ker.id` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `equipment.version` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `location` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `operation_type` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `operator` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `site_notes` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `tasks[0].description` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `tasks[0].prompt` | meta/episodes.jsonl, meta/tasks.jsonl | meta/episodes.jsonl, meta/tasks.jsonl | meta/episodes.jsonl, meta/tasks.jsonl | meta/episodes.jsonl, meta/tasks.jsonl | meta/episodes.jsonl, meta/tasks.jsonl | meta/episodes.jsonl, meta/tasks.jsonl |

## LeRobot v3.0 (WSL2 Ubuntu, Python 3.12.3, lerobot 0.7.0)

| source field | lerobot_v3.0/all | lerobot_v3.0/success_only | lerobot_v3.0/valid_only |
|---|---|---|---|
| `episodes[0].id` | **lost** | **lost** | **lost** |
| `episodes[1].id` | **lost** | **lost** | **lost** |
| `episodes[2].id` | **lost** | **lost** | **lost** |
| `equipment.embodiments.arms.id` | **lost** | **lost** | **lost** |
| `equipment.embodiments.lifter.home` | **lost** | **lost** | **lost** |
| `equipment.embodiments.lifter.id` | **lost** | **lost** | **lost** |
| `equipment.embodiments.lifter.mechanism` | **lost** | **lost** | **lost** |
| `equipment.embodiments.lifter.unit` | **lost** | **lost** | **lost** |
| `equipment.id` | **lost** | **lost** | **lost** |
| `equipment.leader.ker.firmware_version` | **lost** | **lost** | **lost** |
| `equipment.leader.ker.id` | **lost** | **lost** | **lost** |
| `equipment.version` | **lost** | **lost** | **lost** |
| `location` | **lost** | **lost** | **lost** |
| `operation_type` | **lost** | **lost** | **lost** |
| `operator` | **lost** | **lost** | **lost** |
| `site_notes` | **lost** | **lost** | **lost** |
| `tasks[0].description` | **lost** | **lost** | **lost** |
| `tasks[0].prompt` | meta/episodes/chunk-000/file-000.parquet, meta/tasks.parquet | meta/episodes/chunk-000/file-000.parquet, meta/tasks.parquet | meta/episodes/chunk-000/file-000.parquet, meta/tasks.parquet |
