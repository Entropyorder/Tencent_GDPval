# 金融文件取证与 GDPval 题目构建

本项目处理金融类 PDF、Word、Excel 和 CSV：先抽取通用 query 并检索 Top 20，
再由 Pi CLI 通过自定义工具和 Skill 选择最终附件、生成辅助文件并反向构建题目，
最后生成并验收 Golden Solution。

## 三人协作结构

代码按负责人拆成三个可独立运行的阶段：

```text
workflows/
├── stage1_query_retrieval/       # 负责人 A：query + Top 20
│   ├── run.py
│   ├── rename_attachments.py
│   └── README.md
├── stage2_task_builder/          # 负责人 B：Pi CLI 选附件和反向出题
│   ├── run.py
│   ├── prepare_workspace.py
│   ├── run_pi_task.sh
│   ├── pi_tool_backend.py
│   ├── pi-agent/                # 自定义模型、Extension 和 Skill
│   ├── validate_task_output.py
│   └── README.md
└── stage3_golden_solution/       # 负责人 C：Golden Solution
    ├── run.py
    ├── run_claude_golden_solution.sh
    ├── validate_golden_solution.py
    └── README.md
```

阶段之间只通过文件交接，不导入其他阶段的实现：

1. Stage 1 输出 `queries.json` 和 `retrieval/manifest.json`。
2. Stage 2 读取检索清单，输出 `task_NNN/final/`。
3. Stage 3 读取最终题目与附件，输出 `task_NNN/golden solution/`。

详细输入输出契约见 [workflows/README.md](workflows/README.md) 和各阶段 README。
`scripts/run_end_to_end.py` 仅负责依次调用三个公共入口，不放阶段业务逻辑。

## 项目目录

```text
腾讯_GDPval金法医/
├── data/
│   └── source_documents/        # 379 个原始文件
├── prompts/                     # Stage 1/3 中文提示词
├── src/finance_forensics/       # 文档抽取、编目、query 和检索核心库
├── workflows/                   # 三个隔离工作流
├── scripts/
│   └── run_end_to_end.py        # 跨阶段总编排器
├── tests/
├── docs/
└── output/                      # 全部业务输出
```

`data/source_documents/` 用于在本地存放 379 个原始文件。Git 仓库只提交该
目录的 `.gitkeep` 占位文件，不上传原始文档。

现有 `output/tasks/task_001`、`task_002` 及其最终产物保持原位置不变。

## 环境

```bash
cd /home/ghpan/project/腾讯_GDPval金法医
source .venv/bin/activate
```

Inferera Base URL、模型和 API 密钥从权限为 `600` 的 `.env` 读取。Pi 和
Stage 3 的 Claude Code 均使用 `.env` 中配置的模型；密钥不写入 Skill、
提示词、代码或输出。

Stage 1 和 Stage 3 的提示词集中在 `prompts/`：

- `文档编目.md`
- `文档编目输入模板.md`
- `通用查询生成.md`
- `通用查询输入模板.md`
- `Claude黄金答案生成.md`

Stage 2 的规则已经迁入
`workflows/stage2_task_builder/pi-agent/skills/gdpval-task-builder/SKILL.md`。

## 文档编目

```bash
# 查看输入，不调用模型
finance-forensics inventory

# 本地抽取单个文件，不调用模型
finance-forensics inspect data/source_documents/0001_20220309110518725.pdf

# 显式执行全量编目
finance-forensics run --workers 4
```

编目输出位于 `output/catalog/document_catalog.json` 和 `.jsonl`。

## Stage 1：Query 与 Top 20

从一个或多个已编目文件生成通用 query，再进行检索：

```bash
.venv/bin/python workflows/stage1_query_retrieval/run.py \
  --source-file 0050_54e6ee7d4a7c74b71d8ea7502bfc5416.pdf \
  --output-dir output/stage1_query_retrieval
```

使用已有 query JSON：

```bash
.venv/bin/python workflows/stage1_query_retrieval/run.py \
  --queries output/queries/query_test.json \
  --output-dir output/stage1_query_retrieval
```

输出：

```text
output/stage1_query_retrieval/
├── queries.json
└── retrieval/
    ├── manifest.json
    └── query_NNN/files/         # 每条 query 恰好 20 个候选
```

检索使用中文语义向量、字符 TF-IDF、类型匹配和 Cross-Encoder 重排，不使用
生成式大模型逐个挑选文件。

## Stage 2：Pi 题目构建

首次运行安装固定版本的 Pi CLI：

```bash
npm ci --ignore-scripts
```

```bash
.venv/bin/python workflows/stage2_task_builder/run.py \
  --manifest output/stage1_query_retrieval/retrieval/manifest.json \
  --tasks-dir output/tasks
```

只准备工作区、暂不调用 Pi：

```bash
.venv/bin/python workflows/stage2_task_builder/run.py \
  --manifest output/stage1_query_retrieval/retrieval/manifest.json \
  --tasks-dir output/tasks \
  --task-index 2 \
  --stop-after prepare
```

每题只访问自己的20个候选文件。Pi 先比较并保存题目方向，再选择候选，并生成
且实际选用1至3个辅助附件；最终固化10至17个 attachments 后，按最终顺序
重新编号，
再分别反向编写 `workflow.md` 和 query。Pi 禁用通用 shell/write/edit，只能
调用 Stage 2 的受控工具。workflow 至少包含12个工作步骤；query 固定为
“任务背景、具体任务、交付要求”三段，其中“具体任务”只能用一个整体叙述
段落，不列步骤或具体分析方法，交付文件不超过5个。

验收已有题目：

```bash
.venv/bin/python workflows/stage2_task_builder/validate_task_output.py \
  --workspace output/tasks \
  --task 002
```

## Stage 3：Golden Solution

```bash
.venv/bin/python workflows/stage3_golden_solution/run.py \
  --tasks-dir output/tasks \
  --task-index 2
```

Stage 3 实际创建 query 指定的交付文件，并校验文件可打开、内容完整性、
Excel 公式、来源追踪和哈希。验收已有结果：

```bash
.venv/bin/python workflows/stage3_golden_solution/validate_golden_solution.py \
  --workspace output/tasks \
  --task 002
```

## 端到端编排

总编排器只是依次运行三个阶段：

```bash
.venv/bin/python scripts/run_end_to_end.py \
  --queries output/queries/query_test.json \
  --run-id finance_batch_001
```

也可以从单条 query 或源文件开始：

```bash
.venv/bin/python scripts/run_end_to_end.py \
  --query "需要分析的初始金融工作任务" \
  --run-id finance_single_001

.venv/bin/python scripts/run_end_to_end.py \
  --source-file 0050_54e6ee7d4a7c74b71d8ea7502bfc5416.pdf \
  --run-id finance_source_001
```

新运行目录：

```text
output/pipeline_runs/<run_id>/
├── stage1/
│   ├── queries.json
│   └── retrieval/
├── stage2/
│   └── tasks/
└── pipeline_manifest.json
```

Stage 3 的结果写在 `stage2/tasks/task_NNN/golden solution/`，与对应题目保持
在同一个任务目录。中断后使用相同参数并增加 `--resume`。可用
`--stop-after stage1|stage2|stage3` 或 `--dry-run` 控制执行。

## 测试

```bash
.venv/bin/pytest -q
```
