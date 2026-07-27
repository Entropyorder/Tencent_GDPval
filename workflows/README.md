# 三阶段工作流

本目录按三位负责人拆分。阶段之间只通过磁盘文件交接，不互相导入对方的
Python 实现。

| 阶段 | 负责目录 | 输入 | 主要输出 |
|---|---|---|---|
| Stage 1 | `stage1_query_retrieval/` | 源文件名、query 或 query JSON | `queries.json`、`retrieval/manifest.json`、Top 20 文件 |
| Stage 2 | `stage2_task_builder/` | Stage 1 的 `retrieval/manifest.json` | `task_NNN/final/query.json`、附件和内部清单 |
| Stage 3 | `stage3_golden_solution/` | Stage 2 的 `task_NNN/` | `task_NNN/golden solution/` |

各目录中的 `run.py` 是唯一公共入口，README 是该阶段的文件契约。根目录
`scripts/run_end_to_end.py` 只负责编排三个入口，不应增加阶段内部业务逻辑。

提示词仍集中在项目根目录 `prompts/`。Stage 1 使用通用查询提示词，Stage 2
使用复杂题目构建提示词，Stage 3 使用黄金答案生成提示词。
