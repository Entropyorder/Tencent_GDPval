from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil

from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-base"

DOCUMENT_TYPE_LABELS = {
    "annual_report": "年度报告 经营与财务表现",
    "prospectus": "招股说明书 融资与投资风险",
    "audit_report": "审计报告 财务报表核查",
    "financial_statement": "财务报表 经营与财务表现",
    "rating_report": "信用评级报告 信用风险分析",
    "regulatory_inquiry": "监管问询 信息披露核查",
    "regulatory_reply": "监管回复 信息披露核查",
    "legal_opinion": "法律意见 合规风险审阅",
    "bond_report": "债券报告 信用与偿债风险",
    "offering_document": "发行文件 融资与投资风险",
    "statistical_data": "统计数据 行业与市场分析",
    "business_data": "业务数据 经营与财务表现",
    "research_report": "研究报告 观点与证据评估",
    "policy_document": "政策文件 政策影响与合规分析",
    "other": "综合资料 风险分析",
}

TYPE_RELEVANCE_RULES = (
    (
        ("信用", "评级"),
        {
            "rating_report": 1.0,
            "bond_report": 0.7,
            "annual_report": 0.35,
            "financial_statement": 0.3,
        },
    ),
    (
        ("审计", "核查"),
        {
            "audit_report": 1.0,
            "financial_statement": 0.75,
            "regulatory_reply": 0.5,
        },
    ),
    (
        ("监管问询", "信息披露核查"),
        {
            "regulatory_inquiry": 1.0,
            "regulatory_reply": 1.0,
            "policy_document": 0.55,
            "annual_report": 0.4,
        },
    ),
    (
        ("融资材料", "发行材料", "投资风险分析"),
        {
            "prospectus": 1.0,
            "offering_document": 1.0,
            "bond_report": 0.8,
            "rating_report": 0.55,
        },
    ),
    (
        ("债券信用", "偿债风险分析"),
        {
            "bond_report": 1.0,
            "rating_report": 0.8,
            "offering_document": 0.65,
            "annual_report": 0.4,
        },
    ),
    (
        ("法律风险", "合规审阅"),
        {
            "legal_opinion": 1.0,
            "policy_document": 0.75,
            "regulatory_inquiry": 0.55,
            "regulatory_reply": 0.55,
        },
    ),
    (
        ("统计数据", "行业数据", "市场数据"),
        {
            "statistical_data": 1.0,
            "business_data": 0.7,
            "research_report": 0.6,
        },
    ),
    (
        ("研究观点", "证据评估"),
        {
            "research_report": 1.0,
            "statistical_data": 0.55,
        },
    ),
    (
        ("政策影响", "政策分析"),
        {
            "policy_document": 1.0,
            "regulatory_inquiry": 0.5,
            "regulatory_reply": 0.5,
        },
    ),
    (
        ("经营", "财务", "业绩"),
        {
            "annual_report": 1.0,
            "financial_statement": 1.0,
            "business_data": 0.95,
            "audit_report": 0.65,
            "rating_report": 0.5,
        },
    ),
)

QUERY_FOCUS_RULES = (
    (
        ("信用", "评级"),
        "企业信用评级报告 信用风险分析 主体信用等级 评级展望 经营风险 "
        "财务风险 偿债能力 流动性",
    ),
    (
        ("审计", "核查"),
        "审计报告 财务报表核查 会计政策 财务数据 审计意见 风险事项",
    ),
    (
        ("监管问询", "信息披露核查"),
        "监管问询回复 信息披露核查 财务真实性 业务合规 风险说明",
    ),
    (
        ("融资材料", "发行材料", "投资风险分析"),
        "融资发行材料 投资风险分析 募集资金 经营财务 风险因素",
    ),
    (
        ("债券信用", "偿债风险分析"),
        "债券信用分析 偿债能力 债务结构 流动性 融资风险",
    ),
    (
        ("法律风险", "合规审阅"),
        "法律意见 合规审阅 法律风险 监管要求 重大事项",
    ),
    (
        ("统计数据", "行业数据", "市场数据"),
        "行业市场统计数据 趋势分析 结构变化 经营指标",
    ),
    (
        ("研究观点", "证据评估"),
        "研究报告 观点证据 行业趋势 风险判断 投资分析",
    ),
    (
        ("政策影响", "政策分析"),
        "政策文件 政策影响 合规要求 业务影响 风险应对",
    ),
    (
        ("经营", "财务", "业绩"),
        "企业经营与财务表现分析 经营业绩 财务状况 盈利能力 资产负债 "
        "现金流 风险变化",
    ),
)


def load_queries(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("query JSON must be an array")
    queries = []
    for index, item in enumerate(payload, start=1):
        query = item if isinstance(item, str) else item.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"query item {index} does not contain a non-empty query")
        queries.append(query.strip())
    return queries


def load_document_catalog(path):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        record
        for record in records
        if record.get("processing", {}).get("status") == "success"
        and record.get("summary")
    ]


def catalog_attachment_filename(record, used_names=None):
    filename = record.get("suggested_filename") or record["source_filename"]
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError(
            f"document {record.get('document_id', '<unknown>')} has no usable filename"
        )
    filename = filename.strip()
    if Path(filename).name != filename or filename in {".", ".."}:
        raise ValueError(f"unsafe catalog filename: {filename}")

    used_names = used_names if used_names is not None else set()
    if filename not in used_names:
        return filename

    path = Path(filename)
    document_id = str(record.get("document_id") or "duplicate").removeprefix("doc_")
    candidate = f"{path.stem}_{document_id[:8]}{path.suffix}"
    counter = 2
    while candidate in used_names:
        candidate = f"{path.stem}_{document_id[:8]}_{counter}{path.suffix}"
        counter += 1
    return candidate


def build_document_text(record):
    document_type = record.get("document_type") or "other"
    parts = [
        f"文档类型：{DOCUMENT_TYPE_LABELS.get(document_type, document_type)}",
        f"业务主题：{record.get('business_topic', '')}",
        f"行业：{record.get('industry', '')}",
        f"关键词：{' '.join(record.get('keywords', []))}",
        f"内容摘要：{record.get('summary', '')}",
    ]
    return "\n".join(part for part in parts if part.rsplit("：", 1)[-1].strip())


def catalog_fingerprint(records, texts, model_name):
    digest = hashlib.sha256(model_name.encode())
    for record, text in zip(records, texts):
        digest.update(record["document_id"].encode())
        digest.update(b"\0")
        digest.update(text.encode())
        digest.update(b"\0")
    return digest.hexdigest()


def normalize_rows(matrix):
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.clip(norms, 1e-12, None)


def minmax(values):
    values = np.asarray(values, dtype=np.float32)
    low = float(values.min())
    high = float(values.max())
    if high - low < 1e-12:
        return np.zeros_like(values)
    return (values - low) / (high - low)


def type_relevance(query, document_type):
    for triggers, weights in TYPE_RELEVANCE_RULES:
        if any(trigger in query for trigger in triggers):
            return weights.get(document_type, 0.0)
    return 0.0


def retrieval_query_text(query):
    for triggers, focus in QUERY_FOCUS_RULES:
        if any(trigger in query for trigger in triggers):
            return focus
    return query


def profile_quality_relevance(query, record):
    if "企业" in query:
        if record.get("company_name"):
            score = 1.0
        elif record.get("subject_name"):
            score = 0.55
        else:
            score = 0.15
    else:
        score = 1.0
    if record.get("needs_review"):
        score *= 0.35
    return score


def load_or_create_document_embeddings(
    records,
    texts,
    model,
    model_name,
    cache_path,
):
    fingerprint = catalog_fingerprint(records, texts, model_name)
    cache_path = Path(cache_path)
    if cache_path.exists():
        with np.load(cache_path, allow_pickle=False) as cached:
            cached_fingerprint = str(cached["fingerprint"].item())
            cached_ids = cached["document_ids"].tolist()
            expected_ids = [record["document_id"] for record in records]
            if cached_fingerprint == fingerprint and cached_ids == expected_ids:
                return normalize_rows(cached["embeddings"]), True

    embeddings = normalize_rows(
        np.vstack(list(model.passage_embed(texts, batch_size=64)))
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path,
        fingerprint=np.array(fingerprint),
        document_ids=np.array(
            [record["document_id"] for record in records], dtype=str
        ),
        embeddings=embeddings,
    )
    return embeddings, False


def attachment_record(record, rank, scores, attachment_filename):
    result = {
        "rank": rank,
        "source_filename": record["source_filename"],
        "attachment_filename": attachment_filename,
        "document_id": record["document_id"],
        "suggested_filename": record.get("suggested_filename"),
        "document_type": record.get("document_type"),
        "subject_name": record.get("subject_name"),
        "business_topic": record.get("business_topic"),
        "summary": record.get("summary"),
        "hybrid_score": round(float(scores["hybrid"]), 6),
        "first_stage_score": round(float(scores["first_stage"]), 6),
        "rerank_score": round(float(scores["rerank"]), 6),
        "dense_score": round(float(scores["dense"]), 6),
        "lexical_score": round(float(scores["lexical"]), 6),
        "type_score": round(float(scores["type"]), 6),
        "profile_quality_score": round(float(scores["profile_quality"]), 6),
    }
    return {key: value for key, value in result.items() if value is not None}


def retrieve_attachments(
    queries_path,
    catalog_path,
    input_dir,
    output_dir,
    top_k=20,
    model_name=DEFAULT_EMBEDDING_MODEL,
    rerank_model_name=DEFAULT_RERANK_MODEL,
    candidate_k=80,
    rerank_weight=0.60,
    profile_quality_weight=0.10,
    dense_weight=0.70,
    lexical_weight=0.15,
    type_weight=0.15,
):
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    if abs(dense_weight + lexical_weight + type_weight - 1.0) > 1e-6:
        raise ValueError("retrieval weights must sum to 1")
    if candidate_k < top_k:
        raise ValueError("candidate_k must be greater than or equal to top_k")
    if not 0 <= rerank_weight <= 1:
        raise ValueError("rerank_weight must be between 0 and 1")
    if not 0 <= profile_quality_weight <= 1:
        raise ValueError("profile_quality_weight must be between 0 and 1")

    queries_path = Path(queries_path).resolve()
    catalog_path = Path(catalog_path).resolve()
    input_dir = Path(input_dir).resolve()
    output_dir = Path(output_dir).resolve()
    queries = load_queries(queries_path)
    search_queries = [retrieval_query_text(query) for query in queries]
    records = load_document_catalog(catalog_path)
    if not records:
        raise ValueError("catalog does not contain successful documents with summaries")
    top_k = min(top_k, len(records))
    texts = [build_document_text(record) for record in records]

    cache_root = Path(__file__).resolve().parents[2] / ".cache"
    model_cache = cache_root / "fastembed"
    embedding_cache = (
        cache_root / f"document_embeddings_{model_name.replace('/', '__')}.npz"
    )
    model = TextEmbedding(
        model_name=model_name,
        cache_dir=str(model_cache),
        threads=min(os.cpu_count() or 1, 8),
    )
    document_embeddings, cache_hit = load_or_create_document_embeddings(
        records,
        texts,
        model,
        model_name,
        embedding_cache,
    )
    query_embeddings = normalize_rows(
        np.vstack(list(model.query_embed(search_queries, batch_size=16)))
    )
    reranker = TextCrossEncoder(
        model_name=rerank_model_name,
        cache_dir=str(model_cache),
        threads=min(os.cpu_count() or 1, 8),
    )

    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        sublinear_tf=True,
        norm="l2",
    )
    lexical_matrix = vectorizer.fit_transform(texts + search_queries)
    document_lexical = lexical_matrix[: len(records)]
    query_lexical = lexical_matrix[len(records) :]

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "queries_file": str(queries_path),
        "catalog_file": str(catalog_path),
        "input_dir": str(input_dir),
        "document_count": len(records),
        "top_k": top_k,
        "retrieval": {
            "dense_model": model_name,
            "rerank_model": rerank_model_name,
            "rerank_weight": rerank_weight,
            "profile_quality_weight": profile_quality_weight,
            "candidate_k": min(candidate_k, len(records)),
            "dense_weight": dense_weight,
            "lexical_method": "character_tfidf_2_4gram",
            "lexical_weight": lexical_weight,
            "document_type_weight": type_weight,
            "embedding_cache_hit": cache_hit,
        },
        "queries": [],
    }

    for query_index, query in enumerate(queries, start=1):
        search_query = search_queries[query_index - 1]
        dense_scores = document_embeddings @ query_embeddings[query_index - 1]
        lexical_scores = (
            document_lexical @ query_lexical[query_index - 1].T
        ).toarray().ravel()
        type_scores = np.array(
            [
                type_relevance(query, record.get("document_type") or "other")
                for record in records
            ],
            dtype=np.float32,
        )
        profile_quality_scores = np.array(
            [profile_quality_relevance(query, record) for record in records],
            dtype=np.float32,
        )
        first_stage_scores = (
            dense_weight * minmax(dense_scores)
            + lexical_weight * minmax(lexical_scores)
            + type_weight * type_scores
        )
        candidate_count = min(candidate_k, len(records))
        candidate_order = np.argsort(
            -first_stage_scores, kind="stable"
        )[:candidate_count]
        rerank_raw = np.array(
            list(
                reranker.rerank(
                    search_query,
                    [texts[int(index)] for index in candidate_order],
                    batch_size=16,
                )
            ),
            dtype=np.float32,
        )
        rerank_scores = minmax(rerank_raw)
        candidate_relevance_scores = (
            rerank_weight * rerank_scores
            + (1 - rerank_weight) * first_stage_scores[candidate_order]
        )
        candidate_final_scores = (
            (1 - profile_quality_weight) * candidate_relevance_scores
            + profile_quality_weight * profile_quality_scores[candidate_order]
        )
        local_order = np.argsort(-candidate_final_scores, kind="stable")[:top_k]
        order = candidate_order[local_order]

        query_dir = output_dir / f"query_{query_index:03d}"
        files_dir = query_dir / "files"
        if query_dir.exists():
            shutil.rmtree(query_dir)
        files_dir.mkdir(parents=True)
        results = []
        used_attachment_filenames = set()
        for rank, record_index in enumerate(order, start=1):
            record = records[int(record_index)]
            source_path = input_dir / record["source_filename"]
            if not source_path.is_file():
                raise FileNotFoundError(f"cataloged source file is missing: {source_path}")
            attachment_filename = catalog_attachment_filename(
                record, used_attachment_filenames
            )
            used_attachment_filenames.add(attachment_filename)
            shutil.copy2(source_path, files_dir / attachment_filename)
            results.append(
                attachment_record(
                    record,
                    rank,
                    {
                        "hybrid": candidate_final_scores[local_order[rank - 1]],
                        "first_stage": first_stage_scores[record_index],
                        "rerank": rerank_scores[local_order[rank - 1]],
                        "dense": dense_scores[record_index],
                        "lexical": lexical_scores[record_index],
                        "type": type_scores[record_index],
                        "profile_quality": profile_quality_scores[record_index],
                    },
                    attachment_filename,
                )
            )

        query_payload = {
            "query_index": query_index,
            "query": query,
            "retrieval_query": search_query,
            "results": results,
        }
        (query_dir / "ranking.json").write_text(
            json.dumps(query_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest["queries"].append(
            {
                "query_index": query_index,
                "query": query,
                "retrieval_query": search_query,
                "directory": str(query_dir),
                "results": results,
            }
        )

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest
