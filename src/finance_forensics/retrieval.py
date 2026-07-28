from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil

from fastembed import TextEmbedding
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_SEMANTIC_WEIGHT = 0.75
DEFAULT_KEYWORD_WEIGHT = 0.25


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
    return str(record.get("summary") or "").strip()


def build_keyword_document_text(record):
    fields = (
        ("业务主题", record.get("business_topic")),
        ("文档关键词", " ".join(record.get("keywords", []))),
        ("内容摘要", record.get("summary")),
    )
    return "\n".join(
        f"{label}：{value}"
        for label, value in fields
        if isinstance(value, str) and value.strip()
    )


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


def combine_retrieval_scores(
    semantic_values,
    keyword_values,
    semantic_weight=DEFAULT_SEMANTIC_WEIGHT,
    keyword_weight=DEFAULT_KEYWORD_WEIGHT,
):
    if abs(semantic_weight + keyword_weight - 1.0) > 1e-6:
        raise ValueError("retrieval weights must sum to 1")
    return (
        semantic_weight * minmax(semantic_values)
        + keyword_weight * minmax(keyword_values)
    )


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
        "semantic_score": round(float(scores["semantic"]), 6),
        "keyword_score": round(float(scores["keyword"]), 6),
    }
    return {key: value for key, value in result.items() if value is not None}


def retrieve_attachments(
    queries_path,
    query_keywords,
    catalog_path,
    input_dir,
    output_dir,
    top_k=20,
    model_name=DEFAULT_EMBEDDING_MODEL,
    semantic_weight=DEFAULT_SEMANTIC_WEIGHT,
    keyword_weight=DEFAULT_KEYWORD_WEIGHT,
    keyword_metadata=None,
):
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    if not 0 <= semantic_weight <= 1 or not 0 <= keyword_weight <= 1:
        raise ValueError("retrieval weights must be between 0 and 1")
    if abs(semantic_weight + keyword_weight - 1.0) > 1e-6:
        raise ValueError("retrieval weights must sum to 1")

    queries_path = Path(queries_path).resolve()
    catalog_path = Path(catalog_path).resolve()
    input_dir = Path(input_dir).resolve()
    output_dir = Path(output_dir).resolve()
    queries = load_queries(queries_path)
    if len(query_keywords) != len(queries):
        raise ValueError("query keyword count must match query count")
    if any(not keywords for keywords in query_keywords):
        raise ValueError("each query must have at least one extracted keyword")

    records = load_document_catalog(catalog_path)
    if not records:
        raise ValueError("catalog does not contain successful documents with summaries")
    top_k = min(top_k, len(records))
    summaries = [build_document_text(record) for record in records]
    keyword_document_texts = [
        build_keyword_document_text(record) for record in records
    ]
    keyword_queries = [" ".join(keywords) for keywords in query_keywords]

    cache_root = Path(__file__).resolve().parents[2] / ".cache"
    model_cache = cache_root / "fastembed"
    catalog_key = hashlib.sha256(str(catalog_path).encode()).hexdigest()[:12]
    embedding_cache = (
        cache_root
        / (
            f"summary_embeddings_{model_name.replace('/', '__')}_"
            f"{catalog_key}.npz"
        )
    )
    model = TextEmbedding(
        model_name=model_name,
        cache_dir=str(model_cache),
        threads=min(os.cpu_count() or 1, 8),
    )
    document_embeddings, cache_hit = load_or_create_document_embeddings(
        records,
        summaries,
        model,
        model_name,
        embedding_cache,
    )
    query_embeddings = normalize_rows(
        np.vstack(list(model.query_embed(queries, batch_size=16)))
    )

    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        sublinear_tf=True,
        norm="l2",
    )
    keyword_matrix = vectorizer.fit_transform(
        keyword_document_texts + keyword_queries
    )
    document_keywords = keyword_matrix[: len(records)]
    query_keyword_vectors = keyword_matrix[len(records) :]

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
            "semantic_model": model_name,
            "semantic_input": "raw_query_to_catalog_summary",
            "semantic_weight": semantic_weight,
            "keyword_method": "llm_keywords_to_catalog_profile_char_tfidf_2_4gram",
            "keyword_weight": keyword_weight,
            "keyword_extraction": keyword_metadata or {},
            "embedding_cache_hit": cache_hit,
        },
        "queries": [],
    }

    for query_index, query in enumerate(queries, start=1):
        semantic_raw = document_embeddings @ query_embeddings[query_index - 1]
        keyword_raw = (
            document_keywords @ query_keyword_vectors[query_index - 1].T
        ).toarray().ravel()
        semantic_scores = minmax(semantic_raw)
        keyword_scores = minmax(keyword_raw)
        final_scores = combine_retrieval_scores(
            semantic_raw,
            keyword_raw,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
        )
        order = np.argsort(-final_scores, kind="stable")[:top_k]

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
                        "hybrid": final_scores[record_index],
                        "semantic": semantic_scores[record_index],
                        "keyword": keyword_scores[record_index],
                    },
                    attachment_filename,
                )
            )

        query_payload = {
            "query_index": query_index,
            "query": query,
            "keywords": query_keywords[query_index - 1],
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
                "keywords": query_keywords[query_index - 1],
                "directory": str(query_dir),
                "results": results,
            }
        )

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest
