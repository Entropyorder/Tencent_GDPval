import importlib.util
import json
from pathlib import Path

import openpyxl
import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "stage2_task_builder"
    / "pi_tool_backend.py"
)
SPEC = importlib.util.spec_from_file_location("pi_tool_backend", SCRIPT_PATH)
BACKEND = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BACKEND)


def make_workspace(tmp_path):
    task_dir = tmp_path / "task_999"
    (task_dir / "candidates").mkdir(parents=True)
    (task_dir / "extracted").mkdir()
    candidates = []
    for rank in range(1, 21):
        filename = f"{rank:02d}__company_{rank:02d}_report.txt"
        extracted_name = f"{rank:02d}__company_{rank:02d}_report.md"
        (task_dir / "candidates" / filename).write_text(
            f"公司{rank}财务与经营报告原始内容\n",
            encoding="utf-8",
        )
        (task_dir / "extracted" / extracted_name).write_text(
            "# 财务概况\n"
            f"公司{rank}在报告期内披露营业收入、现金流、债务结构和经营风险。\n"
            "# 风险事项\n"
            f"公司{rank}需要关注流动性、行业周期和资本开支压力。\n",
            encoding="utf-8",
        )
        candidates.append(
            {
                "rank": rank,
                "document_id": f"doc_{rank:02d}",
                "attachment_filename": filename,
                "candidate_path": f"candidates/{filename}",
                "extracted_path": f"extracted/{extracted_name}",
                "document_type": "年度报告",
                "subject_name": f"公司{rank}",
                "business_topic": "财务与经营风险",
                "summary": f"公司{rank}的财务表现、现金流与风险事项概述。",
            }
        )
    manifest = {
        "schema_version": "1.0",
        "task_id": "999",
        "candidate_count": 20,
        "original_query": "分析企业财务质量和风险。",
        "retrieval_query": "企业财务质量 风险",
        "candidates": candidates,
    }
    (task_dir / "candidate_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    return task_dir


def call(task_dir, action, **params):
    return BACKEND.handle(
        {"action": action, "cwd": str(task_dir), "params": params}
    )


def directions():
    return {
        "alternatives": [
            {
                "title": "信用组合压力测试",
                "thesis": (
                    "基于多家企业的财务、现金流和债务材料构建统一口径，"
                    "完成信用风险分层、压力情景测算和投资组合限额建议，"
                    "重点处理报告期差异、信息缺口以及行业周期造成的不可比性。"
                    "最终结果服务于投资委员会的持仓调整、观察名单和尽调优先级决策，"
                    "并要求所有指标能够回溯到具体来源和计算过程。"
                ),
                "candidateRanks": list(range(1, 13)),
                "risks": ["报告期和披露口径存在差异"],
            },
            {
                "title": "经营韧性横向比较",
                "thesis": (
                    "围绕收入质量、盈利能力、资本开支和流动性表现开展同业"
                    "横向比较，识别经营韧性来源并形成管理层资源配置建议，"
                    "同时验证异常指标是否由业务结构或一次性事项引起。"
                    "通过业务结构拆分、趋势分析和异常归因形成竞争力排序，"
                    "并为预算配置和经营改善行动提供具有证据基础的判断。"
                ),
                "candidateRanks": list(range(4, 18)),
                "risks": ["行业与业务模式并不完全可比"],
            },
        ],
        "selectedTitle": "信用组合压力测试",
        "selectionReason": (
            "第一方向覆盖的现金流、债务和经营风险证据更完整，能够形成统一"
            "模型、压力情景和组合决策的真实依赖链；第二方向的行业可比性较弱，"
            "部分候选只能提供定性支持，因此选择第一方向更可回答也更具复杂度。"
        ),
    }


def make_query():
    background = (
        "你是受投资委员会委托的高级信用分析师，需要评估一个企业组合在基准与"
        "不利经营环境下的偿债韧性，并形成可复核的组合管理决策。现有附件包括"
        "不同主体和报告期的财务、经营及风险材料，部分材料具有口径差异、信息"
        "重叠或仅提供辅助背景。所有事实、计算输入和判断都必须从附件中提取，"
        "不得联网补充数据；对无法直接统一的项目，应明确假设和处理方法。"
        "委员会尤其关注不同风险驱动因素在压力环境中的相互作用，以及单一主体"
        "风险向组合层面传导的路径。分析既要保留原始披露的可追溯性，也要形成"
        "一致、透明、能够由其他分析师复算的决策框架；不能用简单排名代替对"
        "业务模式、财务结构、数据可靠性和风险缓释条件的专业解释。"
    )
    task_narrative = (
        "请综合全部材料，对目标组合的经营质量、财务韧性、信用风险及压力环境"
        "下的风险传导开展系统评估，在妥善处理主体差异、报告期错配、披露口径"
        "和信息缺口的基础上，形成一套可追溯、可复算且具有专业解释力的分析"
        "框架。最终判断应能够支持投资委员会进行风险分层、组合限额、观察名单"
        "和尽调资源配置决策，并清楚区分附件事实、推导结果、任务假设及专业"
        "判断，为后续独立复核和持续风险监测保留完整依据。"
    )
    delivery = (
        "请提交以下 2 个文件：\n"
        "1. `信用组合风险评估报告.docx`：呈现口径、证据核对、风险判断、"
        "情景结果、组合建议和局限性。\n"
        "2. `信用组合压力测试模型.xlsx`：包含来源索引、标准化数据、计算公式、"
        "情景参数、敏感性分析、评分结果和质量检查。"
    )
    return (
        f"## 任务背景\n{background}\n\n"
        f"## 具体任务\n{task_narrative}\n\n"
        f"## 交付要求\n{delivery}"
    )


def make_workflow():
    tasks = [
        "建立附件索引，识别各主体、报告期、币种、口径和数据来源，并记录缺失项。",
        "设计统一分析口径，将可以比较的利润、现金流、债务和流动性指标映射到标准字段。",
        "交叉核对重复披露与异常变动，区分经营变化、一次性事项和口径调整的影响。",
        "计算核心偿债、杠杆、现金流覆盖和盈利质量指标，并保留计算过程与来源定位。",
        "按业务模式和行业暴露建立可比组，解释不可直接横向比较的指标及替代判断方法。",
        "形成基准风险画像，识别每个主体的主要风险驱动因素、缓释因素和证据强度。",
        "设计至少两个不利情景，明确冲击变量、传导路径、参数依据和组合层面的相关性假设。",
        "在各情景下测算指标变化和风险迁移，开展关键参数敏感性分析并定位临界点。",
        "对定量结果进行跨文件验证，分析结论冲突、信息缺口和模型局限对排序的影响。",
        "建立透明的风险分层或评分框架，说明权重、阈值、例外处理及专业判断覆盖规则。",
        "综合基准和压力结果提出组合限额、观察名单、优先尽调事项及触发条件。",
        "执行独立质量检查，确保引用可追溯、公式可复算、结论与附件证据一致。",
    ]
    task_text = "\n\n".join(
        f"{index}. {task}" for index, task in enumerate(tasks, start=1)
    )
    return "# 工作流程\n\n" + task_text


def test_pi_backend_enforces_order_and_completes_full_workflow(tmp_path):
    task_dir = make_workspace(tmp_path)

    inventory = call(task_dir, "candidate_inventory")
    assert inventory["details"]["candidate_count"] == 20
    search = call(
        task_dir,
        "search_evidence",
        terms=["现金流", "风险"],
        ranks=[1, 2],
        maxHits=8,
    )
    assert search["details"]["hit_count"] >= 2

    with pytest.raises(ValueError, match="set_task_direction"):
        call(
            task_dir,
            "create_generated_attachment",
            filename="情景参数.xlsx",
            format="xlsx",
            purpose="为所有主体提供一致且明确的压力测试参数假设。",
            sourceDocumentIds=[],
            payload=json.dumps(
                {"sheets": [{"name": "参数", "rows": [["变量", "基准"], ["收入", 1]]}]}
            ),
        )

    call(task_dir, "set_task_direction", **directions())
    with pytest.raises(ValueError, match="financial_resource_inventory"):
        call(
            task_dir,
            "create_generated_attachment",
            filename="情景参数.xlsx",
            format="xlsx",
            purpose="为所有主体提供一致且明确的压力测试参数假设。",
            sourceDocumentIds=["doc_01", "doc_02"],
            templateReference="investment-comparison-xlsx",
            designRationale=(
                "借鉴多方案参数矩阵和输入区布局，只写任务给定假设，不复制模板数据。"
            ),
            payload=json.dumps(
                {"sheets": [{"name": "参数", "rows": [["变量", "基准"], ["收入", 1]]}]}
            ),
        )

    resources = call(task_dir, "financial_resource_inventory")
    assert resources["details"]["skill"] == (
        "generating-financial-analysis-reports"
    )
    assert resources["details"]["template_count"] == 6
    with pytest.raises(ValueError, match="does not support Stage 2 xlsx files"):
        call(
            task_dir,
            "create_generated_attachment",
            filename="不兼容模板.xlsx",
            format="xlsx",
            purpose="验证文字报告模板不能被错误用于电子表格附件。",
            sourceDocumentIds=["doc_01", "doc_02"],
            templateReference="financial-analysis-report-doc",
            designRationale=(
                "尝试将文字报告模板用于电子表格文件，并声明沿用其章节结构和版式层级；"
                "此处仅用于验证资源格式兼容性校验能够在生成文件前稳定生效。"
            ),
            payload=json.dumps(
                {"sheets": [{"name": "参数", "rows": [["变量", "基准"], ["收入", 1]]}]}
            ),
        )
    generated = call(
        task_dir,
        "create_generated_attachment",
        filename="情景参数.xlsx",
        format="xlsx",
        purpose="为所有主体提供一致且明确的压力测试参数假设。",
        sourceDocumentIds=["doc_01", "doc_02"],
        templateReference="investment-comparison-xlsx",
        designRationale=(
            "借鉴投资方案对比模板的横向情景矩阵、说明页和输入区布局，"
            "只呈现题目假设及来源，不复制模板数据或生成压力测试结论。"
        ),
        payload=json.dumps(
            {
                "sheets": [
                    {
                        "name": "参数",
                        "rows": [
                            ["变量", "基准情景", "不利情景"],
                            ["收入冲击", 0, -0.1],
                            ["成本冲击", 0, 0.05],
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    assert generated["details"]["filename"] == "情景参数.xlsx"
    assert generated["details"]["template_reference"] == (
        "investment-comparison-xlsx"
    )
    workbook = openpyxl.load_workbook(task_dir / "generated" / "情景参数.xlsx")
    assert workbook.sheetnames == ["说明", "参数"]
    assert workbook["参数"]["C2"].value == -0.1
    assert workbook["说明"]["B4"].value == "investment-comparison-xlsx"
    assert workbook["参数"]["A1"].fill.fgColor.rgb == "00404040"
    workbook.close()

    attachments = []
    selected_ranks = [3, 5, 7, 9, 10, 11, 12, 1, 2]
    for position, rank in enumerate(selected_ranks, start=1):
        role = "core" if position <= 2 else (
            "purposeful_noise" if position == 9 else "supporting"
        )
        attachments.append(
            {
                "candidateRank": rank,
                "role": role,
                "rationale": "该文件提供主体财务、现金流或风险证据并支持交叉核对。",
                "expectedUse": "用于统一口径、指标计算和证据复核。",
            }
        )
    without_generated = attachments + [
        {
            "candidateRank": 4,
            "role": "supporting",
            "rationale": "该文件补充主体经营信息，可用于跨文件验证和异常识别。",
            "expectedUse": "用于统一口径、指标计算和证据复核。",
        }
    ]
    with pytest.raises(ValueError, match="at least 1 generated attachment"):
        call(
            task_dir,
            "assemble_final_attachments",
            attachments=without_generated,
        )

    attachments.append(
        {
            "generatedFilename": "情景参数.xlsx",
            "role": "generated",
            "rationale": "该文件补充跨主体一致的压力参数，避免答题者自行猜测假设。",
            "expectedUse": "用于基准和不利情景的统一测算。",
        }
    )
    assembly = call(
        task_dir,
        "assemble_final_attachments",
        attachments=attachments,
    )
    assert assembly["details"]["attachment_count"] == 10
    assert assembly["details"]["generated_count"] == 1
    assert assembly["details"]["filenames"] == [
        "01__company_03_report.txt",
        "02__company_05_report.txt",
        "03__company_07_report.txt",
        "04__company_09_report.txt",
        "05__company_10_report.txt",
        "06__company_11_report.txt",
        "07__company_12_report.txt",
        "08__company_01_report.txt",
        "09__company_02_report.txt",
        "10__情景参数.xlsx",
    ]

    evidence = (
        "# 证据矩阵\n\n"
        + "\n".join(
            f"- 步骤{index}：使用附件{min(index, 9)}的财务概况与风险事项，"
            "结合情景参数表核对口径、来源、报告期和指标计算。"
            for index in range(1, 13)
        )
        + "\n\n各文件的报告期和主体不同，建模时必须保留原始值并记录标准化调整。"
    )
    quality = (
        "# 质量审查\n\n"
        "题目完全由固化附件回答，不需要外部数据。十二个步骤形成数据整理、"
        "交叉验证、建模、压力测试、敏感性分析、风险分层和决策建议的依赖链，"
        "预计专业人员需要十小时以上。生成附件只给出假设，没有预先计算答案。"
        "题干没有泄漏关键数值、最终结论或干扰项身份，两个交付文件均可由附件"
        "复核。附件数量、来源边界、哈希、三段结构和连续编号已逐项检查。"
        * 3
    )
    result = call(
        task_dir,
        "finalize_task",
        queryMarkdown=make_query(),
        workflowMarkdown=make_workflow(),
        evidenceMatrixMarkdown=evidence,
        qualityReviewMarkdown=quality,
    )

    assert result["terminate"] is True
    assert result["details"]["attachments"] == 10
    assert result["details"]["generated_attachments"] == 1
    assert result["details"]["workflow_steps"] == 12
    assert result["details"]["deliverable_files"] == 2
    assert (task_dir / "final" / "query.md").is_file()
    assert (task_dir / "final" / "workflow.md").is_file()
    assert (
        task_dir / "final" / "internal" / "financial_resources.json"
    ).is_file()
    selection = json.loads(
        (
            task_dir / "final" / "internal" / "selection_manifest.json"
        ).read_text(encoding="utf-8")
    )
    generated_record = next(
        item for item in selection["attachments"] if item["origin"] == "generated"
    )
    assert generated_record["skill_reference"] == (
        "generating-financial-analysis-reports"
    )
    assert generated_record["template_reference"] == (
        "investment-comparison-xlsx"
    )
