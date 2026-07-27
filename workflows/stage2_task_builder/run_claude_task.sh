#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASK_ID="${1:-}"
TASKS_DIR="${2:-$PROJECT_ROOT/output/tasks}"

if [[ ! "$TASK_ID" =~ ^[0-9]{3}$ ]]; then
  echo "usage: $0 NNN [tasks_dir]" >&2
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
PROMPT_FILE="$PROJECT_ROOT/prompts/Claude复杂题目构建.md"

if [[ ! -f "$TASK_DIR/candidate_manifest.json" ]]; then
  echo "task workspace is not prepared: $TASK_DIR" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
cd "$TASK_DIR"

claude --bare -p "$(cat "$TASK_DIR/TASK.md")" \
  --system-prompt "$(cat "$PROMPT_FILE")" \
  --model "$INFERERA_MODEL" \
  --max-budget-usd "${CLAUDE_TASK_MAX_BUDGET_USD:-30}" \
  --permission-mode acceptEdits \
  --allowedTools "Read,Glob,Grep,Bash,Write,Edit,Agent" \
  --output-format json \
  > "$LOG_DIR/task_$TASK_ID.json"

"$PROJECT_ROOT/.venv/bin/python" \
  "$PROJECT_ROOT/workflows/stage2_task_builder/export_query_markdown.py" \
  --task "$TASK_ID" \
  --workspace "$TASKS_DIR"

printf 'claude_task_complete task=%s log=%s\n' \
  "$TASK_ID" "$LOG_DIR/task_$TASK_ID.json"
