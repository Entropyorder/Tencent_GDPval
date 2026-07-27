# JSON 结构设计

最终文件是 JSON 数组，每个原始文件对应一个记录。核心字段保持在顶层，便于
直接导入数据库或表格；可审计细节放在嵌套对象中。

```json
{
  "schema_version": "1.0",
  "document_id": "doc_a13f99213fd1b280",
  "source_filename": "0001_20220309110518725.pdf",
  "suggested_filename": "山西证券_新三板市场动态_研究报告_2022年_doc_a13f9921.pdf",
  "summary": "山西证券发布的新三板市场周度研究资料，覆盖2022年2月28日至3月4日期间的挂牌企业、市场交易和重点公司动态。文档围绕新三板市场成交、融资、行业表现及企业公告展开，对当周主要事件和市场变化进行归纳，并提示相关企业经营与信息披露情况，可用于了解该期间新三板市场运行和研究机构关注重点。",
  "subject_name": "山西证券股份有限公司",
  "company_name": "山西证券股份有限公司",
  "business_topic": "新三板市场动态",
  "document_type": "research_report",
  "reporting_period": "2022-02-28至2022-03-04",
  "publish_date": "2022-03-09",
  "industry": "证券",
  "market": "新三板",
  "keywords": ["新三板", "挂牌公司", "市场周报"],
  "confidence": 0.92,
  "needs_review": false,
  "review_reasons": [],
  "source": {
    "absolute_path": "/path/to/original.pdf",
    "extension": ".pdf",
    "size_bytes": 123456,
    "sha256": "a13f...",
    "crawler_url": "https://example.com/file.pdf",
    "crawler_title": "搜索结果标题",
    "crawler_query": "新三板 年度报告 filetype:pdf",
    "collected_at": "2026-07-25T07:43:41.508Z"
  },
  "extraction": {
    "status": "success",
    "method": "pymupdf",
    "characters": 30000,
    "total_units": 60,
    "units_read": 20,
    "truncated": true,
    "warnings": []
  },
  "renaming": {
    "llm_suggested_filename": "山西证券_新三板市场动态_研究报告_2022年.pdf",
    "normalized_filename": "山西证券_新三板市场动态_研究报告_2022年_doc_a13f9921.pdf",
    "applied": false
  },
  "processing": {
    "status": "success",
    "model": "deepseek-v4-flash",
    "prompt_version": "document_profile_v1",
    "processed_at": "2026-07-25T17:00:00+08:00",
    "duration_seconds": 8.3
  }
}
```

## 关键约束

- `document_id`：基于文件 SHA-256 生成，文件不变则 ID 不变。
- `summary`：信息充分时建议 250 至 450 字，代码层保证不超过 500 个字符。
- `suggested_filename`：保留原扩展名并追加短 ID，不直接重命名原文件。
- `status`：单文件失败也会写入检查点，避免整批任务丢失。
- `source`：保留原 URL、搜索词、哈希和大小，便于追溯。
- `confidence` 与 `needs_review`：用于后续人工抽查排序。
- 最终 JSON 会递归省略值为 `null` 的字段，减少无效字段噪声。
