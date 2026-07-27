#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKFLOW_DIR="$PROJECT_ROOT/workflows/stage2_task_builder"
TASK_ID="${1:-}"
TASKS_DIR="${2:-$PROJECT_ROOT/output/tasks}"

if [[ ! "$TASK_ID" =~ ^[0-9]{3}$ ]]; then
  echo "usage: $0 NNN [tasks_dir]" >&2
  exit 2
fi

set -a
source "$PROJECT_ROOT/.env"
set +a

PI_BIN="${PI_BIN:-$PROJECT_ROOT/node_modules/.bin/pi}"
if [[ ! -x "$PI_BIN" ]]; then
  echo "Pi CLI is not installed: $PI_BIN" >&2
  echo "run: npm ci --ignore-scripts" >&2
  exit 1
fi

export PI_CODING_AGENT_DIR="$WORKFLOW_DIR/pi-agent"
export PI_OFFLINE=1
export PI_TELEMETRY=0
export GDPVAL_PYTHON="$PROJECT_ROOT/.venv/bin/python"

TASKS_DIR="$(cd "$TASKS_DIR" && pwd)"
TASK_DIR="$TASKS_DIR/task_$TASK_ID"
LOG_DIR="$TASKS_DIR/logs"
SKILL_FILE="$WORKFLOW_DIR/pi-agent/skills/gdpval-task-builder/SKILL.md"
EXTENSION_FILE="$WORKFLOW_DIR/pi-agent/extensions/gdpval-tools.ts"

if [[ ! -f "$TASK_DIR/candidate_manifest.json" ]]; then
  echo "task workspace is not prepared: $TASK_DIR" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
cd "$TASK_DIR"

"$PI_BIN" \
  --mode json \
  --no-session \
  --no-context-files \
  --no-builtin-tools \
  --no-extensions \
  --extension "$EXTENSION_FILE" \
  --no-skills \
  --skill "$SKILL_FILE" \
  --no-prompt-templates \
  --provider inferera \
  --model "$INFERERA_MODEL" \
  --tools "candidate_inventory,read_candidate,search_evidence,set_task_direction,create_generated_attachment,assemble_final_attachments,finalize_task" \
  "/skill:gdpval-task-builder 执行当前TASK.md对应的完整Stage 2任务。必须从20个候选开始，先确定方向和最终附件，再反向编写query，并以finalize_task验收通过结束。" \
  > "$LOG_DIR/task_${TASK_ID}_pi.jsonl" \
  2> "$LOG_DIR/task_${TASK_ID}_pi.stderr.log"

printf 'pi_task_complete task=%s log=%s\n' \
  "$TASK_ID" "$LOG_DIR/task_${TASK_ID}_pi.jsonl"
