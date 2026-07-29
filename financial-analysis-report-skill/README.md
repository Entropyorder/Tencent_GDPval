# Financial Analysis Report Skill

一个面向中文管理场景的可执行财务分析报告 Skill。输入 JSON 数据后，自动生成纯黑白、严格中英文字体、首行缩进和黑色三线表的 Word 报告，并输出结构化校验结果。

## 目录

```text
financial-analysis-report-skill/
├─ SKILL.md
├─ scripts/
│  ├─ report_style.py
│  ├─ render_report.py
│  └─ validate_report.py
├─ style/report_style.yaml
├─ references/
│  ├─ format_spec.md
│  └─ financial_writing_guide.md
├─ examples/
│  ├─ sample_financial_data.json
│  └─ sample_financial_analysis_report.docx
├─ tests/
└─ internal/
```

## 快速使用

```bash
pip install python-docx lxml pytest
python scripts/render_report.py \
  --input examples/sample_financial_data.json \
  --output examples/sample_financial_analysis_report.docx
python scripts/validate_report.py \
  examples/sample_financial_analysis_report.docx \
  --output internal/validation_report.json
pytest -q
```

## 输入数据

参考 `examples/sample_financial_data.json`。本期与上期必须使用相同单位和会计口径。企业名称、期间、编制部门、报告日期、数据属性均可配置。

## 输出特点

- 中文正文：宋体，小四（12 pt）
- 英文与数字：Times New Roman，12 pt
- 正文：1.5 倍行距、首行缩进 2 个汉字、两端对齐
- 表格：纯黑色三线表，无竖线、无彩色底纹
- 内容：核心结论、总体表现、盈利、偿债、营运、现金流、风险、建议、口径说明
- 校验：字体、字号、缩进、行距、章节、表格数量和三线表边框

示例数据为模拟数据，仅用于展示 Skill 能力。
