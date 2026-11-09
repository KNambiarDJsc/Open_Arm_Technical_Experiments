# After-fix field survey (commit bc34001)

Same command and source as survey_baseline.md. Filtered-out episode ids and operator, location and site_notes (withheld by default) are expected to be absent.

## LeRobot v2.1 and GR00T (Windows, lerobot 0.3.3)

| source field | lerobot_v2.1/all | lerobot_v2.1/success_only | lerobot_v2.1/valid_only | gr00t/all | gr00t/success_only | gr00t/valid_only |
|---|---|---|---|---|---|---|
| `episodes[0].id` | meta/openarm.json | **lost** | meta/openarm.json | meta/openarm.json | **lost** | meta/openarm.json |
| `episodes[1].id` | meta/openarm.json | meta/openarm.json | **lost** | meta/openarm.json | meta/openarm.json | **lost** |
| `episodes[2].id` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.embodiments.arms.id` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.embodiments.lifter.home` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.embodiments.lifter.id` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.embodiments.lifter.mechanism` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.embodiments.lifter.unit` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.id` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.leader.ker.firmware_version` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.leader.ker.id` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.version` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `location` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `operation_type` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `operator` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `site_notes` | **lost** | **lost** | **lost** | **lost** | **lost** | **lost** |
| `tasks[0].description` | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `tasks[0].prompt` | meta/episodes.jsonl, meta/openarm.json, meta/tasks.jsonl | meta/episodes.jsonl, meta/openarm.json, meta/tasks.jsonl | meta/episodes.jsonl, meta/openarm.json, meta/tasks.jsonl | meta/episodes.jsonl, meta/openarm.json, meta/tasks.jsonl | meta/episodes.jsonl, meta/openarm.json, meta/tasks.jsonl | meta/episodes.jsonl, meta/openarm.json, meta/tasks.jsonl |

## LeRobot v3.0 (WSL2 Ubuntu, lerobot 0.7.0)

| source field | lerobot_v3.0/all | lerobot_v3.0/success_only | lerobot_v3.0/valid_only |
|---|---|---|---|
| `episodes[0].id` | meta/openarm.json | **lost** | meta/openarm.json |
| `episodes[1].id` | meta/openarm.json | meta/openarm.json | **lost** |
| `episodes[2].id` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.embodiments.arms.id` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.embodiments.lifter.home` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.embodiments.lifter.id` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.embodiments.lifter.mechanism` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.embodiments.lifter.unit` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.id` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.leader.ker.firmware_version` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.leader.ker.id` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `equipment.version` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `location` | **lost** | **lost** | **lost** |
| `operation_type` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `operator` | **lost** | **lost** | **lost** |
| `site_notes` | **lost** | **lost** | **lost** |
| `tasks[0].description` | meta/openarm.json | meta/openarm.json | meta/openarm.json |
| `tasks[0].prompt` | meta/episodes/chunk-000/file-000.parquet, meta/openarm.json, meta/tasks.parquet | meta/episodes/chunk-000/file-000.parquet, meta/openarm.json, meta/tasks.parquet | meta/episodes/chunk-000/file-000.parquet, meta/openarm.json, meta/tasks.parquet |
