# Stage 3：Golden Solution

## 职责

1. 读取 Stage 2 已验收的 query 和最终附件。
2. 通过 **Pi CLI + Skill**（builtin 工具）实际创建 query 指定的 1 至 5 个交付文件。
3. 生成内部来源追踪、质量报告和哈希清单。
4. 检查文件可打开、内容长度、占位符、Excel 公式、清单哈希，并后置扫描黑白（B/W）。
5. 发生确定性校验失败时，最多自动修复两轮。

本阶段不得改变 Stage 2 的 query 或附件。结构镜像 Stage 2（`run_pi_task.sh` + Skill
+ 后置 validator），但**不锁定工具**：agent 使用 Pi 的通用工具（Read/Write/Edit/Bash/
Glob/Grep）+ `golden-solution` Skill 引导；skill 的 `render.py`/`preextract_attachments.py`
作为 agent 经 Bash 调用的支撑脚本。

## 运行

```bash
.venv/bin/python workflows/stage3_golden_solution/run.py \
  --tasks-dir output/tasks \
  --task-index 2
```

可重复传入 `--task-index`；不传时处理目录中所有已完成的 Stage 2 任务。
中断后加 `--resume`。已有但未通过验收的结果会自动使用修复模式，也可显式
传入 `--repair`。

底层脚本（与 Stage 2 的 `run_pi_task.sh` 对称）：

```bash
bash workflows/stage3_golden_solution/run_pi_golden_solution.sh 002 output/tasks
```

环境与依赖：`.env` 需配 `INFERERA_API_KEY` / `INFERERA_BASE_URL` / `INFERERA_MODEL`；
Pi 运行时由 `package.json` 的 `@earendil-works/pi-coding-agent` 提供（`node_modules/.bin/pi`）；
Python 依赖见项目 `pyproject.toml`，另需 `python-docx` / `openpyxl` / `pypdf` / `PyMuPDF`
（支撑脚本会按需自装 `python-docx`/`openpyxl`）。

## 输入契约

```text
<tasks-dir>/task_NNN/final/
├── query.json
├── query.md
├── attachments/
└── internal/
```

## 输出契约

```text
<tasks-dir>/task_NNN/golden solution/
├── <query 中明确指定的 1 至 5 个交付文件>
└── internal/
    ├── source_traceability.md
    ├── validation_report.json
    └── solution_manifest.json
```

单独验收已有答案：

```bash
.venv/bin/python workflows/stage3_golden_solution/validate_golden_solution.py \
  --workspace output/tasks --task 002
# 严格黑白（彩色违规计为失败）：
.venv/bin/python workflows/stage3_golden_solution/validate_golden_solution.py \
  --workspace output/tasks --task 002 --strict-bw error
```

## 目录组成

- `run.py` — 编排器：发现已完成 Stage 2 任务 → `run_pi_golden_solution.sh` → `validate_golden_solution.py`。
- `run_pi_golden_solution.sh` — Pi 调用脚本（镜像 Stage 2 `run_pi_task.sh`，去掉 locked-tools flags，保留 builtin 工具；含 create + 2 轮 repair 循环）。
- `pi-agent/models.json` — Pi 模型配置（inferera / deepseek-v4-flash）。
- `pi-agent/skills/golden-solution/SKILL.md` — Skill 主体（角色/输入边界/工作方法/交付要求/内部质量文件/完成闭环）。launcher 注入 `$GDPVAL_PYTHON` / `$GDPVAL_STAGE3_DIR` / `$GDPVAL_TASKS_DIR` / `$TASK_ID` 供 agent 经 Bash 调支撑脚本与校验器。
- `render.py` — 黑白渲染器（content.json → docx/xlsx/pptx/md/csv，`_is_grey` 强制去蓝），agent 简单 B/W 路径调用。
- `preextract_attachments.py` — 附件→文本预览（`golden solution/_extracted/_att_*.txt`），含 GBK/GB18030 自检测。
- `validate_golden_solution.py` — 确定性校验器（docx/xlsx/pdf/pptx/csv/md + 占位符 + 活公式 + B/W 后置扫描 + manifest 哈希）。
- `templates/{legal,business,general}/` — 结构模板。
- `references/style-semi-2026Q1.md` — ref-semi 彩色参考风格包规格。

## 负责人边界

本阶段负责人主要维护本目录与 `pi-agent/skills/golden-solution/SKILL.md`。只消费
Stage 2 的最终目录，不回写或重构 Stage 1/2 的业务代码。`prompts/Claude黄金答案生成.md`
为旧 `claude --bare -p` 路径的弃用存档，不再驱动本阶段。
