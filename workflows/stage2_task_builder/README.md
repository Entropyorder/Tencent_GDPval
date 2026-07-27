# Stage 2：Pi 题目构建

## 职责

1. 读取 Stage 1 的 Top 20 清单。
2. 创建相互隔离的任务工作区并抽取候选全文。
3. 使用 Pi CLI、项目 Skill 和受控自定义工具确定题目方向。
4. 从20个候选中选择文件，并按需生成0至3个辅助文件。
5. 固化10至17个最终附件后，反向生成三段式 query。
6. 生成选择清单、证据矩阵和质量审查，并执行确定性验收。

本阶段不做 Top 20 检索，也不生成 Golden Solution。

## Pi 运行时

项目固定使用 `@earendil-works/pi-coding-agent`，首次运行前安装：

```bash
npm ci --ignore-scripts
```

模型从 `.env` 读取 `INFERERA_API_KEY` 和 `INFERERA_MODEL`。项目级模型配置在：

```text
pi-agent/models.json
```

密钥只通过环境变量解析，不写入配置文件、日志命令或 Git。

Pi `0.82.1` 的上游锁文件仍包含 `brace-expansion@5.0.7` 的高危 DoS 审计项。
本阶段禁用了包含 glob 能力在内的全部内置工具，只开放参数受限的项目工具，
因此不向模型暴露该依赖的输入面；升级 Pi 时应重新执行 `npm audit` 并复核。

## Skill 和自定义工具

```text
pi-agent/
├── models.json
├── skills/gdpval-task-builder/SKILL.md
└── extensions/gdpval-tools.ts
```

Pi 使用 `--no-builtin-tools`，不能调用通用 shell、write 或 edit。全部读写只能
通过以下工具：

| 工具 | 作用 |
|---|---|
| `candidate_inventory` | 获取20个候选的完整边界和摘要 |
| `read_candidate` | 按rank读取抽取全文片段 |
| `search_evidence` | 跨候选搜索证据、口径和冲突 |
| `set_task_direction` | 保存至少两个方向并确定最终方向 |
| `create_generated_attachment` | 生成受控的MD/TXT/CSV/XLSX辅助附件 |
| `assemble_final_attachments` | 复制最终附件、计算哈希并写选择清单 |
| `finalize_task` | 反向写query和审计材料并运行验收 |

工具的确定性后端为 `pi_tool_backend.py`。它强制“先方向、再附件、后query”的
执行顺序，限制候选边界、附件数量、生成文件数量、文件格式和写入目录。

## 运行

完整运行：

```bash
.venv/bin/python workflows/stage2_task_builder/run.py \
  --manifest output/stage1_query_retrieval/retrieval/manifest.json \
  --tasks-dir output/tasks
```

只准备第2个工作区，不调用 Pi：

```bash
.venv/bin/python workflows/stage2_task_builder/run.py \
  --manifest output/stage1_query_retrieval/retrieval/manifest.json \
  --tasks-dir output/tasks \
  --task-index 2 \
  --stop-after prepare
```

可重复传入 `--task-index`。中断后加 `--resume`，重新准备选中工作区用
`--force`。Pi 的 JSONL 事件日志保存在 `<tasks-dir>/logs/task_NNN_pi.jsonl`。

## 输入契约

`--manifest` 必须是 Stage 1 的 `retrieval/manifest.json`，每个选中 query
必须恰好包含20个候选结果及可访问的附件路径。

## 输出契约

```text
<tasks-dir>/
├── logs/
└── task_NNN/
    ├── candidate_manifest.json
    ├── candidates/              # 20个候选文件的链接
    ├── extracted/               # 候选全文
    ├── working/                 # 方向选择过程
    ├── generated/               # 尚未装配的生成附件
    ├── TASK.md
    └── final/
        ├── query.json
        ├── query.md
        ├── attachments/         # 10至17个最终附件
        └── internal/
            ├── direction_plan.json
            ├── selection_manifest.json
            ├── evidence_matrix.md
            └── quality_review.md
```

`query.json` 只包含一条 `query`；`query.md` 与其文本严格一致。题目必须包含
“任务背景、具体任务、交付要求”三段、至少10个连续步骤，以及1至5个具名
交付文件。

单独验收已有任务：

```bash
.venv/bin/python workflows/stage2_task_builder/validate_task_output.py \
  --workspace output/tasks \
  --task 002
```

## 负责人边界

本阶段负责人维护本目录、根目录 `package.json` 和 Pi 版本锁。不得依赖
Stage 1 的 Python 内部函数，只读取检索清单；不得修改 Stage 3 的解题规则。
