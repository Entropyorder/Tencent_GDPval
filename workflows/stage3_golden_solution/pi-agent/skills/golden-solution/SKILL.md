---
name: golden-solution
description: 在当前task_NNN工作区读取Stage2已固化的final/query.md与final/attachments，实际创建query指定的交付文件与golden solution/internal三件质量文件，并自跑确定性校验通过后结束。用于Stage3 Golden Solution解题，不改变query或附件。
---

# Golden Solution 生成（Stage3）

把当前 `task_NNN` 当作唯一工作边界。必须完成实际文件，不要只给计划或自然语言
结论。本 Skill 不锁定工具，你可以使用 Pi 的通用工具（Read/Write/Edit/Bash/Glob/Grep）。
所有输出只能写入 `golden solution/`，不得改动 `final/`、`attachments/`、`_extracted/`
或题目其他已有文件。

## 环境变量（launcher 已注入，直接用）

- `$GDPVAL_PYTHON`：项目虚拟环境解释器（用它跑 Python，保证依赖与编码一致）。
- `$GDPVAL_STAGE3_DIR`：Stage3 工作流目录绝对路径，本目录下的支撑脚本/模板/参考都在此。
- `$GDPVAL_TASKS_DIR`：tasks 目录绝对路径（= 当前题目目录的父目录）。
- `$GDPVAL_PROJECT_ROOT`：项目根目录。
- `$GDPVAL_FINANCIAL_REPORT_SKILL_DIR`：自然财务写作与 Word 生成 Skill。
- `$GDPVAL_FINANCIAL_TEMPLATE_DIR`：真实财务 Word/Excel 模板和资源清单。
- 当前题目编号 `$TASK_ID`、当前题目目录 `$PWD`（= `$GDPVAL_TASKS_DIR/task_$TASK_ID`）。

支撑脚本：

| 用途 | 命令 |
|---|---|
| 附件预抽取为文本 | `"$GDPVAL_PYTHON" "$GDPVAL_STAGE3_DIR/preextract_attachments.py" --case "$PWD"` |
| 简单 B/W 渲染 | `"$GDPVAL_PYTHON" "$GDPVAL_STAGE3_DIR/render.py" <content.json> -o "golden solution" [--pack word-A\|word-B\|word-C\|word-ref\|excel-A\|excel-B\|excel-C\|excel-ref]` |
| 确定性校验 | `"$GDPVAL_PYTHON" "$GDPVAL_STAGE3_DIR/validate_golden_solution.py" --workspace "$GDPVAL_TASKS_DIR" --task "$TASK_ID"` |

模板在 `$GDPVAL_STAGE3_DIR/templates/{legal,business,general}/`；参考风格包在
`$GDPVAL_STAGE3_DIR/references/style-semi-2026Q1.md`。

财务类交付同时使用 `generating-financial-analysis-reports` Skill 和
`$GDPVAL_FINANCIAL_TEMPLATE_DIR/template_manifest.json`。launcher 已加载两个
Skill；本 Skill 负责事实、公式、来源和交付闭环，财务报告 Skill 负责自然写作、
正式 Word 版式和三线表。

## 一、角色与目标

你是资深从业者与交付质量负责人。当前题目的 query 和附件已经确定。你的任务不是
修改题目，而是完整执行题目，生成一套可由资深专业人员直接评审的 Golden Solution。

必须实际创建 query 指定的全部交付文件，不能只写答案提纲、过程说明或示例。

## 二、输入边界

1. 只使用当前题目目录中的：
   - `final/query.md`（GDPval 布局）或 `query.md`（裸 case 布局）
   - `final/query.json` 或 `task_metadata.json`（取交付文件清单）
   - `final/attachments/` 或 `attachments/`（附件）
   - `golden solution/_extracted/_att_*.txt`（附件文本预览，**优先读它**，快且准）
2. 不得访问其他题目目录，不得联网补充事实。
3. 附件未披露的数据必须标记为缺失（"当前资料不支持/需补正"），不得编造；情景参数
   附件中的数值可以作为题目给定假设使用。
4. 事实、任务假设、计算结果和专业判断必须清楚区分。

## 三、工作方法

1. 先读 query 与 `_extracted/_index.json`，确认最终交付文件名及附件清单。
2. 若 `golden solution/_extracted/` 尚未生成，先经 Bash 跑预抽取：
   ```bash
   "$GDPVAL_PYTHON" "$GDPVAL_STAGE3_DIR/preextract_attachments.py" --case "$PWD"
   ```
   然后**优先读 `_extracted/_att_*.txt` 文本预览**定位数据（已由 Python 用 openpyxl/
   python-docx 精确解码，单元格值可信）；只在预览截断或需核对格式时，用
   Bash+`"$GDPVAL_PYTHON" -c "from openpyxl import load_workbook; ..."` 读原文件核对。
   不要用 Read 工具直接啃 .xlsx/.docx 二进制（慢且易错）。
3. 建立统一数据底稿，记录主体、报告期、口径、单位、来源附件和 sheet/页码/行项。
4. 对缺失数据、不同报告期和不同会计口径设置显式标记，不得用静默填充替代。
5. 所有计算（评分、税额、比率、汇率、保本线、归因等）必须由底稿数据驱动；
   Excel 中保留**活公式**（`cell.data_type=='f'`），不得只粘贴最终数值，更不得
   把 `=B4*B5` 写成文本字符串。

## 四、财务 Skill 与真实模板

创建交付物前：

1. 读取 `final/internal/financial_resources.json`；新 Stage 2 任务必须存在。兼容
   旧任务而不存在时，读取
   `$GDPVAL_FINANCIAL_TEMPLATE_DIR/template_manifest.json`。
2. 读取 `$GDPVAL_FINANCIAL_REPORT_SKILL_DIR/SKILL.md`；财务报告还要读取
   `references/financial_writing_guide.md` 与 `references/format_spec.md`。
3. 为每个 Word/Excel/PDF/PPTX/CSV 交付物选择一个格式兼容的模板 ID。只借鉴
   结构、版式、sheet 分层和职业文档习惯，不得复制模板中的企业、项目、数据、
   公式结果或结论。
4. 需要核对模板时，不用 Read 直接读取二进制。Excel 用 openpyxl 查看 sheet、
   冻结窗格、公式和样式；旧 Word 可通过项目提取器抽取标题：

   ```bash
   PYTHONPATH="$GDPVAL_PROJECT_ROOT/src" "$GDPVAL_PYTHON" -c \
     'from finance_forensics.extractors import extract_document; import sys; print(extract_document(sys.argv[1], 12000).text)' \
     "$GDPVAL_FINANCIAL_TEMPLATE_DIR/A财务分析报告模板.doc"
   ```

5. 财务 Word 报告优先复用财务 Skill 的 `report_style.py` 排版原语。只有当附件
   数据完整满足 `examples/sample_financial_data.json` 的字段契约，且报告确实是
   通用管理财务分析时，才直接调用 `render_report.py`；不得为了套生成器补造数据。
6. Excel 模型借鉴真实模板的“说明/来源—输入—计算—情景—结果—检查”分层，
   按题目删减，不机械复制十九个 sheet。输入、公式和判断分区清楚，工作表名称
   应贴合本题业务而不是出现模板原公司的名称。

自然与逼真不等于装饰复杂。正文使用“结论—证据—原因—边界—行动”分析链，
表格与正文互相解释；Excel 保留正常财务人员会使用的说明页、版本日期、单位、
期间、来源、冻结窗格、筛选、数字格式、打印设置和质量检查。不得使用模板腔、
空泛结尾、无来源行业均值或重复复述每个数字。

## 五、交付文件创建

从 query 的"交付要求"或 `task_metadata.deliverable_files` 解析 1–5 个具名文件，在
`golden solution/` 根目录逐一创建。**文件名必须与 query 完全一致**。

### 渲染路径选择

- **简单黑白交付物**（普通报告 .docx、普通数据 .xlsx/.csv，无需活公式/autofilter）：
  调本目录的 `render.py` 走 B/W 保证路径：
  ```bash
  "$GDPVAL_PYTHON" "$GDPVAL_STAGE3_DIR/render.py" content.json -o "golden solution" --pack word-ref
  ```
  先写 `content.json`（schema见下），再调 render.py。render.py 的 `_is_grey`
  守卫会强制去蓝。
- **复杂 .xlsx**（需活公式/多 sheet/autofilter/冻结/页眉带版本/输入-计算分区）：
  用 Bash+openpyxl **直接写**，因为 render.py 当前不写活公式。务必：
  - 比率/税额/汇率等关键格子用真公式（`ws.cell(value="=B4*B5-C6")`，openpyxl 自动
    当代式），data_type 会是 `f`；
  - 输入区（直接取自附件原值）与计算区（公式结果）用单元格底纹或批注区分；
  - 每个底层输入在邻列或"数据来源"sheet 标注来源附件+sheet/页码/行项+口径+单位。
- **.docx 报告**：用 python-docx 直接写或经 render.py；必须有清晰标题层级、
  表格、表格下"数据来源："脚注；不得出现 TODO/待补充/示例数据/占位符。

### content.json schema（render.py 路径用）

```json
{
  "deliverable": "docx",
  "title": "...",
  "subtitle": "...",
  "template": "年度经营分析报告",
  "style_pack": "auto",
  "meta": { "author": "...", "date": "...", "doc_no": "..." },
  "sections": [
    { "type": "heading", "level": 1, "text": "一、公司概况" },
    { "type": "paragraph", "text": "..." },
    { "type": "table", "caption": "表1 近三年营业收入", "headers": [...], "rows": [[...]], "note": "数据来源：附件1。" },
    { "type": "bullet", "items": [...] },
    { "type": "numbered", "items": [...] },
    { "type": "page_break": true }
  ],
  "appendix": [...]
}
```

`deliverable` ∈ docx|xlsx|pptx|md|csv；`style_pack` 可指定 `word-A/B/C/ref`、
`excel-A/B/C/ref`，`auto` 由 render.py 轮换。

### 文件类型要求

**Word**：
1. 清晰标题层级、表格、必要的来源脚注或来源列；
2. 完整专业报告，不得出现占位符；
3. 结论明确，同时披露材料局限和关键不确定性；
4. 遵守 query 规定的页数和格式要求。

**Excel**：
1. 至少包含 query 指定的全部工作表；
2. 输入区、计算区、输出区用颜色或样式区分；
3. 关键计算保留**活公式**（data_type=='f'），跨表引用清晰，不得全硬编码；
4. 每个底层输入有来源附件、sheet/页码、报告期、口径、单位；
5. 合理数字格式、冻结窗格、自动筛选、列宽（query 要求时）；
6. 评分/测算/敏感性分析与报告结论一致。

**CSV**：UTF-8 BOM；原值不格式化（不加千分位、负数前置 `-`）；比率写
`0.1822(=18.22%)`；公式列保留可读中缀式。

**黑白要求**：所有交付物**不得出现蓝色**字体或底纹。若直接用 openpyxl/python-docx
写（绕过 render.py 守卫），自觉用黑/灰/白；表头可用深灰底白字（如 `404040`），但
不得用蓝色（如 `1F4E78`）。外部校验器会后置扫描 fill/font color，非灰
（RGB 三通道差>20）记违规。

## 六、内部质量文件

除 query 指定的用户交付文件外，在 `golden solution/internal/` 创建：

1. `source_traceability.md`：逐项记录关键输入、来源附件、sheet/页码/行项、口径，
   并映射至交付文件中的表格或单元格。
2. `validation_report.json`：记录各文件能否打开、Word 段落和表格数、Excel
   工作表、非空单元格和活公式数、占位符检查、B/W 检查、发现并修复的问题。
   （外部校验器会覆盖权威版，你先写一份自评。）
3. `solution_manifest.json`：记录每个用户交付文件的 `filename`、`type`、`bytes`、
   `sha256`。sha256 经 Bash 算：
   ```bash
   "$GDPVAL_PYTHON" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "<交付文件>"
   ```
4. `resource_usage.json`：新 Stage 2 任务必须记录：
   - `skill.name` 固定为 `generating-financial-analysis-reports`；
   - `skill.applied_to` 覆盖全部交付文件，并列出实际采用的写作/版式原则；
   - `templates` 中逐项记录模板 `id`、`applied_to`、具体 `adaptations`；
   - `copied_source_data` 必须为 `false`。

内部文件不属于 query 所说的一至五个用户交付物。

## 七、质量门槛与自检

完成前必须逐项检查：

1. query 指定的交付文件一个不少、一个不多；文件名和扩展名完全一致；
2. Word 和 Excel 均可由 Python 库重新打开；
3. 不存在空文件、占位符、损坏压缩包或外部链接依赖；
4. Excel 至少包含**实质活公式**（data_type=='f'，不是 = 开头的文本串），
   与报告结论一致；
5. 每项关键结论能追溯到附件或明确的任务假设；
6. 不改动 `final/`、`attachments/`、`_extracted/` 或题目其他已有文件；
7. 所有输出只能写入 `golden solution/`。
8. `resource_usage.json` 中的模板与交付格式兼容，且没有模板主体或数据残留。

## 八、完成闭环

写完所有交付文件和 internal/ 质量文件后，**自跑外部校验器**：

```bash
"$GDPVAL_PYTHON" "$GDPVAL_STAGE3_DIR/validate_golden_solution.py" \
  --workspace "$GDPVAL_TASKS_DIR" --task "$TASK_ID"
```

- 若 exit 0：完成。
- 若失败：按校验输出**只修校验指出的问题**（不改 query、附件、已正确的结论），
  修完重跑。编排器最多再喂 2 轮外部修复，你应在第一轮自检时尽量一次过。

完成实际文件、internal/ 质量文件、且自跑校验通过后才可以结束。不得以"已完成""校验通过"
等模型自述替代实际校验结果。
