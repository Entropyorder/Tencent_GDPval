# Stage 2：Claude Code 题目构建

## 职责

1. 读取 Stage 1 的 Top 20 清单。
2. 为每道题创建相互隔离的 Claude Code 工作区并抽取候选文件全文。
3. 让 Claude Code 从 20 个候选中选择 10 至 17 个附件。
4. 允许生成最多 3 个明确标记的辅助附件。
5. 生成三段式 query、附件清单和证据链，并执行确定性验收。

本阶段不做 Top 20 检索，也不生成 Golden Solution。

## 运行

完整运行：

```bash
.venv/bin/python workflows/stage2_task_builder/run.py \
  --manifest output/stage1_query_retrieval/retrieval/manifest.json \
  --tasks-dir output/tasks
```

只准备第 2 个工作区，不调用 Claude Code：

```bash
.venv/bin/python workflows/stage2_task_builder/run.py \
  --manifest output/stage1_query_retrieval/retrieval/manifest.json \
  --tasks-dir output/tasks \
  --task-index 2 \
  --stop-after prepare
```

可重复传入 `--task-index`。中断后加 `--resume`，重新准备选中工作区用
`--force`。

## 输入契约

`--manifest` 必须是 Stage 1 的 `retrieval/manifest.json`，每个选中 query
必须恰好包含 20 个候选结果及可访问的附件路径。

## 输出契约

```text
<tasks-dir>/
├── logs/
└── task_NNN/
    ├── candidate_manifest.json
    ├── candidates/              # 20 个候选文件的只读式链接
    ├── extracted/               # 供 Claude 检索的全文
    ├── TASK.md
    └── final/
        ├── query.json
        ├── query.md
        ├── attachments/
        └── internal/
```

`query.json` 只包含一条 `query`；`query.md` 与其文本严格一致。题目必须包含
“任务背景、具体任务、交付要求”三段、至少 10 个连续步骤，以及 1 至 5 个
具名交付文件。

单独验收已有任务：

```bash
.venv/bin/python workflows/stage2_task_builder/validate_task_output.py \
  --workspace output/tasks \
  --task 002
```

## 负责人边界

本阶段负责人主要维护本目录和 `prompts/Claude复杂题目构建.md`。不得依赖
Stage 1 的 Python 内部函数；只读取检索清单。不得修改 Stage 3 的解题规则。
