import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { StringEnum } from "@earendil-works/pi-ai";
import { Type } from "typebox";
import { fileURLToPath } from "node:url";

const backendPath = fileURLToPath(
  new URL("../../pi_tool_backend.py", import.meta.url),
);

type BackendResponse = {
  ok: boolean;
  message?: string;
  details?: unknown;
  terminate?: boolean;
  error?: string;
};

async function callBackend(
  pi: ExtensionAPI,
  action: string,
  params: unknown,
  cwd: string,
  signal?: AbortSignal,
) {
  const python = process.env.GDPVAL_PYTHON || "python3";
  const request = JSON.stringify({ action, params, cwd });
  const result = await pi.exec(
    python,
    [backendPath, "--request-json", request],
    { signal },
  );
  if (result.code !== 0) {
    throw new Error(
      (result.stderr || result.stdout || `backend exited ${result.code}`).trim(),
    );
  }
  let response: BackendResponse;
  try {
    response = JSON.parse(result.stdout) as BackendResponse;
  } catch {
    throw new Error(`invalid backend response: ${result.stdout.slice(0, 1000)}`);
  }
  if (!response.ok) {
    throw new Error(response.error || "Stage 2 backend rejected the operation");
  }
  return {
    content: [{ type: "text" as const, text: response.message || "OK" }],
    details: response.details || {},
    terminate: response.terminate === true,
  };
}

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "candidate_inventory",
    label: "Candidate Inventory",
    description:
      "读取当前题目的20个候选文件清单、摘要、主体、类型和抽取路径。必须作为任务的第一个工具调用。",
    promptSnippet: "读取当前题目的20个候选附件概览",
    promptGuidelines: [
      "先调用 candidate_inventory 获取完整候选边界，不得凭文件名直接确定题目。",
    ],
    parameters: Type.Object({}),
    async execute(_id, params, signal, _update, ctx) {
      return callBackend(pi, "candidate_inventory", params, ctx.cwd, signal);
    },
  });

  pi.registerTool({
    name: "read_candidate",
    label: "Read Candidate",
    description:
      "按候选rank读取抽取全文的指定行区间，用于核对摘要之外的事实、页码或工作表位置。",
    promptSnippet: "按rank读取候选文件的抽取全文片段",
    promptGuidelines: [
      "对进入核心附件集合的文件使用 read_candidate 或 search_evidence 核对原文证据。",
    ],
    parameters: Type.Object({
      rank: Type.Integer({ minimum: 1, maximum: 20 }),
      startLine: Type.Optional(Type.Integer({ minimum: 1 })),
      lineCount: Type.Optional(
        Type.Integer({ minimum: 1, maximum: 400 }),
      ),
    }),
    async execute(_id, params, signal, _update, ctx) {
      return callBackend(pi, "read_candidate", params, ctx.cwd, signal);
    },
  });

  pi.registerTool({
    name: "search_evidence",
    label: "Search Evidence",
    description:
      "在全部或指定候选的抽取全文中搜索1至12个关键词，返回rank、行号、最近标题和上下文。",
    promptSnippet: "跨候选全文检索证据与冲突",
    promptGuidelines: [
      "使用 search_evidence 交叉核对主体、报告期、指标、口径、缺失项和潜在冲突。",
    ],
    parameters: Type.Object({
      terms: Type.Array(Type.String({ minLength: 1 }), {
        minItems: 1,
        maxItems: 12,
      }),
      ranks: Type.Optional(
        Type.Array(Type.Integer({ minimum: 1, maximum: 20 }), {
          minItems: 1,
          maxItems: 20,
        }),
      ),
      maxHits: Type.Optional(
        Type.Integer({ minimum: 1, maximum: 80 }),
      ),
    }),
    async execute(_id, params, signal, _update, ctx) {
      return callBackend(pi, "search_evidence", params, ctx.cwd, signal);
    },
  });

  pi.registerTool({
    name: "set_task_direction",
    label: "Set Task Direction",
    description:
      "保存2至5个不同题目方向及其证据范围、风险，明确选定方向。未完成本步骤不能生成或装配附件。",
    promptSnippet: "比较候选材料后确定题目方向",
    promptGuidelines: [
      "调用 set_task_direction 比较至少两个实质不同的方案，再选择证据覆盖和职业复杂度最佳的方向。",
    ],
    parameters: Type.Object({
      alternatives: Type.Array(
        Type.Object({
          title: Type.String({ minLength: 1 }),
          thesis: Type.String({ minLength: 80 }),
          candidateRanks: Type.Array(
            Type.Integer({ minimum: 1, maximum: 20 }),
            { minItems: 7, maxItems: 17 },
          ),
          risks: Type.Array(Type.String({ minLength: 1 }), {
            minItems: 1,
            maxItems: 10,
          }),
        }),
        { minItems: 2, maxItems: 5 },
      ),
      selectedTitle: Type.String({ minLength: 1 }),
      selectionReason: Type.String({ minLength: 80 }),
    }),
    async execute(_id, params, signal, _update, ctx) {
      return callBackend(pi, "set_task_direction", params, ctx.cwd, signal);
    },
  });

  pi.registerTool({
    name: "create_generated_attachment",
    label: "Create Generated Attachment",
    description:
      "创建最多3个明确标记的辅助附件，支持Markdown、文本、CSV或XLSX。只能提供任务假设或带来源定位的结构化整理，不能预先完成核心分析。",
    promptSnippet: "生成受控的任务假设或来源整理附件",
    promptGuidelines: [
      "仅在可回答性确有缺口时调用 create_generated_attachment，且不得生成核心答案。",
      "CSV payload 使用 {\"rows\":[[...]]}；XLSX payload 使用 {\"sheets\":[{\"name\":\"...\",\"rows\":[[...]]}]}。",
    ],
    parameters: Type.Object({
      filename: Type.String({ minLength: 1 }),
      format: StringEnum(["markdown", "text", "csv", "xlsx"] as const),
      purpose: Type.String({ minLength: 20 }),
      sourceDocumentIds: Type.Array(Type.String(), {
        minItems: 0,
        maxItems: 20,
      }),
      payload: Type.String({
        minLength: 1,
        description:
          "Markdown/text为正文；CSV/XLSX为符合工具说明的JSON字符串。",
      }),
    }),
    async execute(_id, params, signal, _update, ctx) {
      return callBackend(
        pi,
        "create_generated_attachment",
        params,
        ctx.cwd,
        signal,
      );
    },
  });

  pi.registerTool({
    name: "assemble_final_attachments",
    label: "Assemble Final Attachments",
    description:
      "根据已选方向，将10至17个候选/生成文件复制到final/attachments，计算哈希并写selection_manifest。调用后才能反向编写query。",
    promptSnippet: "固化最终附件集合及选择清单",
    promptGuidelines: [
      "先固化附件再写 query；assemble_final_attachments 会拒绝题目方向之外的候选和未登记生成文件。",
    ],
    parameters: Type.Object({
      attachments: Type.Array(
        Type.Object({
          candidateRank: Type.Optional(
            Type.Integer({ minimum: 1, maximum: 20 }),
          ),
          generatedFilename: Type.Optional(Type.String({ minLength: 1 })),
          role: StringEnum(
            ["core", "supporting", "purposeful_noise", "generated"] as const,
          ),
          rationale: Type.String({ minLength: 20 }),
          expectedUse: Type.String({ minLength: 10 }),
        }),
        { minItems: 10, maxItems: 17 },
      ),
    }),
    async execute(_id, params, signal, _update, ctx) {
      return callBackend(
        pi,
        "assemble_final_attachments",
        params,
        ctx.cwd,
        signal,
      );
    },
  });

  pi.registerTool({
    name: "finalize_task",
    label: "Finalize Task",
    description:
      "在最终附件已经固化后，写入反向推导的query.md/query.json、证据矩阵和质量审查，并运行确定性验收。验收通过后终止本次Pi任务。",
    promptSnippet: "写入反向设计的query并完成确定性验收",
    promptGuidelines: [
      "必须以 finalize_task 验收通过作为最后一步；不得用自然语言声称完成。",
    ],
    parameters: Type.Object({
      queryMarkdown: Type.String({ minLength: 800 }),
      evidenceMatrixMarkdown: Type.String({ minLength: 300 }),
      qualityReviewMarkdown: Type.String({ minLength: 300 }),
    }),
    async execute(_id, params, signal, _update, ctx) {
      return callBackend(pi, "finalize_task", params, ctx.cwd, signal);
    },
  });
}
