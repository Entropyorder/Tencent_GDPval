#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKFLOW_DIR="$PROJECT_ROOT/workflows/stage3_golden_solution"
TASK_ID="${1:-}"
TASKS_DIR="${2:-$PROJECT_ROOT/output/tasks}"
MODE="${3:-create}"

if [[ ! "$TASK_ID" =~ ^[0-9]{3}$ ]]; then
  echo "usage: $0 NNN [tasks_dir] [--repair]" >&2
  exit 2
fi
if [[ "$MODE" != "create" && "$MODE" != "--repair" ]]; then
  echo "usage: $0 NNN [tasks_dir] [--repair]" >&2
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
export GDPVAL_PYTHON="${GDPVAL_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"

TASKS_DIR="$(cd "$TASKS_DIR" && pwd)"
TASK_DIR="$TASKS_DIR/task_$TASK_ID"
LOG_DIR="$TASKS_DIR/logs"
SKILL_FILE="$WORKFLOW_DIR/pi-agent/skills/golden-solution/SKILL.md"

if [[ ! -f "$TASK_DIR/final/query.md" ]]; then
  echo "final task is not prepared: $TASK_DIR" >&2
  exit 1
fi
if [[ "$MODE" == "create" && -e "$TASK_DIR/golden solution" ]]; then
  echo "golden solution already exists: $TASK_DIR/golden solution" >&2
  exit 1
fi
if [[ "$MODE" == "--repair" && ! -d "$TASK_DIR/golden solution" ]]; then
  echo "golden solution does not exist: $TASK_DIR/golden solution" >&2
  exit 1
fi

# 注入 SKILL 引用的环境变量（agent 经 Bash 调支撑脚本/校验器时用）
export GDPVAL_STAGE3_DIR="$WORKFLOW_DIR"
export GDPVAL_TASKS_DIR="$TASKS_DIR"
export TASK_ID

mkdir -p "$LOG_DIR"
cd "$TASK_DIR"

run_pi () {
  # $1 = prompt
  "$PI_BIN" \
    --mode json \
    --no-session \
    --no-context-files \
    --no-skills \
    --skill "$SKILL_FILE" \
    --no-prompt-templates \
    --provider inferera \
    --model "$INFERERA_MODEL" \
    "$1" \
    > "$LOG_DIR/task_${TASK_ID}_golden.jsonl" \
    2> "$LOG_DIR/task_${TASK_ID}_golden.stderr.log"
}

validate () {
  "$GDPVAL_PYTHON" \
    "$WORKFLOW_DIR/validate_golden_solution.py" \
    --workspace "$TASKS_DIR" \
    --task "$TASK_ID"
}

if [[ "$MODE" == "create" ]]; then
  set +e
  run_pi "执行当前题目的完整 Golden Solution。严格遵守 SKILL，实际创建 query 指定的全部交付文件与 golden solution/internal 三件质量文件，并自跑外部校验通过后结束。"
  PI_STATUS=$?
  set -e
  if [[ "$PI_STATUS" -ne 0 ]]; then
    echo "warning: initial Pi run exited with $PI_STATUS; validating files" >&2
  fi
fi

for ATTEMPT in 0 1 2; do
  set +e
  VALIDATION_OUTPUT="$(validate 2>&1)"
  VALIDATION_STATUS=$?
  set -e
  if [[ "$VALIDATION_STATUS" -eq 0 ]]; then
    printf '%s\n' "$VALIDATION_OUTPUT"
    printf 'pi_golden_solution_complete task=%s output=%s log=%s\n' \
      "$TASK_ID" "$TASK_DIR/golden solution" \
      "$LOG_DIR/task_${TASK_ID}_golden.jsonl"
    exit 0
  fi
  if [[ "$ATTEMPT" -eq 2 ]]; then
    printf '%s\n' "$VALIDATION_OUTPUT" >&2
    echo "golden solution validation failed after two repairs" >&2
    exit 1
  fi

  REPAIR_NUMBER=$((ATTEMPT + 1))
  set +e
  run_pi "现有 Golden Solution 的外部确定性校验失败。只修复校验指出的问题，不改变 query、附件或已经正确的分析结论。修复实际文件后，重新计算 internal/validation_report.json 和 solution_manifest.json，并重跑外部校验。校验错误如下：

$VALIDATION_OUTPUT"
  PI_STATUS=$?
  set -e
  if [[ "$PI_STATUS" -ne 0 ]]; then
    echo "warning: repair $REPAIR_NUMBER exited with $PI_STATUS; validating files" >&2
  fi
done
