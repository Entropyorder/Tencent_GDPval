#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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

export ANTHROPIC_BASE_URL="${INFERERA_BASE_URL%/v1}"
export ANTHROPIC_API_KEY="$INFERERA_API_KEY"
export ANTHROPIC_AUTH_TOKEN="$INFERERA_API_KEY"
export ANTHROPIC_MODEL="$INFERERA_MODEL"
export ANTHROPIC_DEFAULT_OPUS_MODEL="$INFERERA_MODEL"
export ANTHROPIC_DEFAULT_SONNET_MODEL="$INFERERA_MODEL"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="$INFERERA_MODEL"
export CLAUDE_CODE_SUBAGENT_MODEL="$INFERERA_MODEL"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export CLAUDE_CODE_ATTRIBUTION_HEADER=0
export DISABLE_PROMPT_CACHING=1

TASKS_DIR="$(cd "$TASKS_DIR" && pwd)"
TASK_DIR="$TASKS_DIR/task_$TASK_ID"
LOG_DIR="$TASKS_DIR/logs"
PROMPT_FILE="$PROJECT_ROOT/prompts/Claude黄金答案生成.md"

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

mkdir -p "$LOG_DIR"
cd "$TASK_DIR"

if [[ "$MODE" == "create" ]]; then
  set +e
  claude --bare -p "执行当前题目的完整 Golden Solution。严格遵守系统提示词，实际创建全部文件并完成内部校验。" \
    --system-prompt "$(cat "$PROMPT_FILE")" \
    --model "$INFERERA_MODEL" \
    --effort high \
    --max-budget-usd "${CLAUDE_GOLDEN_MAX_BUDGET_USD:-30}" \
    --permission-mode acceptEdits \
    --allowedTools "Read,Glob,Grep,Bash,Write,Edit,Agent" \
    --output-format json \
    > "$LOG_DIR/task_${TASK_ID}_golden_solution.json"
  CLAUDE_STATUS=$?
  set -e
  if [[ "$CLAUDE_STATUS" -ne 0 ]]; then
    echo "warning: initial Claude run exited with $CLAUDE_STATUS; validating files" >&2
  fi
fi

for ATTEMPT in 0 1 2; do
  set +e
  VALIDATION_OUTPUT="$(
    "$PROJECT_ROOT/.venv/bin/python" \
      "$PROJECT_ROOT/workflows/stage3_golden_solution/validate_golden_solution.py" \
      --workspace "$TASKS_DIR" \
      --task "$TASK_ID" 2>&1
  )"
  VALIDATION_STATUS=$?
  set -e
  if [[ "$VALIDATION_STATUS" -eq 0 ]]; then
    printf '%s\n' "$VALIDATION_OUTPUT"
    printf 'claude_golden_solution_complete task=%s output=%s log=%s\n' \
      "$TASK_ID" "$TASK_DIR/golden solution" \
      "$LOG_DIR/task_${TASK_ID}_golden_solution.json"
    exit 0
  fi
  if [[ "$ATTEMPT" -eq 2 ]]; then
    printf '%s\n' "$VALIDATION_OUTPUT" >&2
    echo "golden solution validation failed after two repairs" >&2
    exit 1
  fi

  REPAIR_NUMBER=$((ATTEMPT + 1))
  set +e
  claude --bare -p "现有 Golden Solution 的外部确定性校验失败。只修复校验指出的问题，不改变 query、附件或已经正确的分析结论。修复实际文件后，重新计算内部 validation_report.json 和 solution_manifest.json。校验错误如下：

$VALIDATION_OUTPUT" \
    --system-prompt "$(cat "$PROMPT_FILE")" \
    --model "$INFERERA_MODEL" \
    --effort high \
    --max-budget-usd "${CLAUDE_GOLDEN_REPAIR_MAX_BUDGET_USD:-8}" \
    --permission-mode acceptEdits \
    --allowedTools "Read,Glob,Grep,Bash,Write,Edit" \
    --output-format json \
    > "$LOG_DIR/task_${TASK_ID}_golden_solution_repair_${REPAIR_NUMBER}.json"
  CLAUDE_STATUS=$?
  set -e
  if [[ "$CLAUDE_STATUS" -ne 0 ]]; then
    echo "warning: repair $REPAIR_NUMBER exited with $CLAUDE_STATUS; validating files" >&2
  fi
done
