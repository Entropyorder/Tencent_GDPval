# Stage 1：Query 与 Top 20

## 职责

1. 从已编目源文件抽取一条通用 query，或接收人工 query/query JSON。
2. 规范化为只包含 `query` 字段的 JSON。
3. 使用语义向量、字符 TF-IDF、类型匹配和 Cross-Encoder 重排。
4. 为每条 query 固定输出 20 个候选文件。

本阶段不选择最终 10 至 17 个附件，也不调用 Claude Code 出题。
从源文件生成时会把正文抽样传给模型，由样本自身的信息结构决定题目方向；
query 只设 600 字符上限，不设最低字数。可通过
`QUERY_LLM_TEMPERATURE` 单独调整生成多样性，默认值为 `0.7`。

## 运行

从源文件生成 query 后检索：

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

也可重复传入 `--query "..."`。中断后加 `--resume`，重建目录用 `--force`。

## 输出契约

```text
<output-dir>/
├── queries.json
├── query_checkpoint.jsonl       # 仅生成 query 时存在
└── retrieval/
    ├── manifest.json
    └── query_NNN/
        └── files/               # 恰好 20 个候选文件
```

Stage 2 只需要读取 `retrieval/manifest.json`；清单中的每条 query 必须有恰好
20 个 `results`。

历史检索结果需要重新套用目录中的语义化名称时：

```bash
.venv/bin/python workflows/stage1_query_retrieval/rename_attachments.py \
  --output-dir output/retrieval
```

## 负责人边界

本阶段负责人主要维护本目录、`src/finance_forensics/query_*`、
`src/finance_forensics/retrieval.py`、`attachment_naming.py` 和
`prompts/通用查询生成.md`。不要修改 Stage 2/3 的生成与验收规则。
