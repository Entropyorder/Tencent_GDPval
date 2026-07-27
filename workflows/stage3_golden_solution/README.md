# Stage 3：Golden Solution

## 职责

1. 读取 Stage 2 已验收的 query 和最终附件。
2. 使用 Claude Code 实际创建 query 指定的 1 至 5 个交付文件。
3. 生成内部来源追踪、质量报告和哈希清单。
4. 检查文件可打开、内容长度、占位符、Excel 公式和清单哈希。
5. 发生确定性校验失败时，最多自动修复两轮。

本阶段不得改变 Stage 2 的 query 或附件。

## 运行

```bash
.venv/bin/python workflows/stage3_golden_solution/run.py \
  --tasks-dir output/tasks \
  --task-index 2
```

可重复传入 `--task-index`；不传时处理目录中所有已完成的 Stage 2 任务。
中断后加 `--resume`。已有但未通过验收的结果会自动使用修复模式，也可显式
传入 `--repair`。

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
  --workspace output/tasks \
  --task 002
```

## 负责人边界

本阶段负责人主要维护本目录和 `prompts/Claude黄金答案生成.md`。只消费
Stage 2 的最终目录，不回写或重构 Stage 1/2 的业务代码。
