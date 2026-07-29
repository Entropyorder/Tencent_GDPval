---
name: generating-financial-analysis-reports
description: Use when an agent must produce a formal Chinese Word financial analysis report from structured company data, especially for management reporting, annual or quarterly reviews, profitability analysis, solvency analysis, operating efficiency, cash flow, or investment decision support.
---

# 生成真实自然的财务分析报告

## 核心原则

报告必须同时满足三项要求：数据口径可追溯、分析语言像专业财务人员写作、Word 版式可直接交付。机械复述数字不属于分析。

## 输入要求

优先使用结构化 JSON，至少包含公司信息、报告期间、本期与上期利润表/资产负债表/现金流量关键数据，以及业务背景。真实数据不得改写；模拟数据必须明确标注“模拟”。字段规范见 `examples/sample_financial_data.json`。

## 执行流程

1. 检查期间、单位、币种和字段完整性。分母为零时写“不可比”，不得编造解释。
2. 先形成“结论—证据—原因—风险—行动”分析链，再生成正文。写作规则见 `references/financial_writing_guide.md`。
3. 按 `references/format_spec.md` 和 `style/report_style.yaml` 生成 Word：正文中文宋体小四，英文和数字 Times New Roman，小四；正文 1.5 倍行距、首行缩进 2 个汉字；表格采用黑色三线表。
4. 执行：

```bash
python scripts/render_report.py \
  --input examples/sample_financial_data.json \
  --output examples/sample_financial_analysis_report.docx
```

5. 执行结构校验，并将结果写入交付目录：

```bash
python scripts/validate_report.py \
  examples/sample_financial_analysis_report.docx \
  --output internal/validation_report.json
```

6. 对 DOCX 执行渲染检查，逐页确认无乱码、截断、表格溢出和页眉页脚错位。未通过视觉检查不得交付。
7. 同步生成 `internal/source_traceability.md`、`internal/validation_report.json`、`internal/solution_manifest.json`。

## 硬性格式规则

- A4 纵向；上 2.6 cm、下 2.4 cm、左 3.0 cm、右 2.6 cm。
- 正文中文 SimSun 12 pt；英文和数字 Times New Roman 12 pt。
- 正文两端对齐，1.5 倍行距，首行缩进 24 pt，段前段后均为 0。
- 标题采用黑体层级；不得使用彩色标题、底纹、艺术字和装饰图标。
- 黑色三线表仅保留顶线、表头下线和底线；禁止竖线及数据行内部横线。
- 表头加粗居中，文字列左对齐，数值列右对齐，单位必须明确。

## 交付门槛

报告至少包括核心结论、总体表现、盈利能力、偿债能力、营运效率、现金流、风险、管理建议和指标口径；至少 5 个三线表。正文必须解释指标变化的业务原因和管理含义，不得只替换公司名称和数字后重复固定句式。
