import json
from pathlib import Path

from fastembed import TextEmbedding
import numpy as np

from .retrieval import DEFAULT_EMBEDDING_MODEL, load_queries, normalize_rows


def randomized_farthest_indices(embeddings, count, seed, random_pool_size=5):
    embeddings = normalize_rows(embeddings)
    total = len(embeddings)
    if not 1 <= count <= total:
        raise ValueError("selection count must be between 1 and the query count")
    if random_pool_size < 1:
        raise ValueError("random pool size must be at least 1")

    generator = np.random.default_rng(seed)
    available = np.ones(total, dtype=bool)
    max_similarity = np.full(total, -np.inf, dtype=np.float32)
    selected = []
    similarity_when_selected = []

    selected_index = int(generator.integers(total))
    for selection_number in range(count):
        if selection_number:
            candidates = np.flatnonzero(available)
            pool_size = min(random_pool_size, len(candidates))
            candidate_scores = max_similarity[candidates]
            pool_positions = np.argpartition(
                candidate_scores, pool_size - 1
            )[:pool_size]
            selected_index = int(generator.choice(candidates[pool_positions]))

        selected.append(selected_index)
        similarity_when_selected.append(
            None
            if selection_number == 0
            else float(max_similarity[selected_index])
        )
        available[selected_index] = False
        similarities = embeddings @ embeddings[selected_index]
        max_similarity = np.maximum(max_similarity, similarities)

    return selected, similarity_when_selected


def select_diverse_queries(
    input_path,
    output_path,
    manifest_path,
    count,
    seed,
    model_name=DEFAULT_EMBEDDING_MODEL,
    random_pool_size=5,
    cache_dir=None,
):
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()
    manifest_path = Path(manifest_path).resolve()
    queries = load_queries(input_path)
    model = TextEmbedding(
        model_name=model_name,
        cache_dir=str(cache_dir) if cache_dir else None,
    )
    embeddings = normalize_rows(
        np.vstack(list(model.query_embed(queries, batch_size=64)))
    )
    selected, similarity_when_selected = randomized_farthest_indices(
        embeddings,
        count=count,
        seed=seed,
        random_pool_size=random_pool_size,
    )

    selected_embeddings = embeddings[selected]
    pairwise = selected_embeddings @ selected_embeddings.T
    np.fill_diagonal(pairwise, -np.inf)
    nearest_similarities = pairwise.max(axis=1)

    query_payload = [{"query": queries[index]} for index in selected]
    manifest = {
        "schema_version": "1.0",
        "input_file": str(input_path),
        "input_query_count": len(queries),
        "selected_query_count": len(selected),
        "selection": {
            "method": "randomized_farthest_point_cosine",
            "semantic_model": model_name,
            "seed": seed,
            "random_pool_size": random_pool_size,
        },
        "items": [
            {
                "selected_index": selected_index,
                "source_query_index": source_index + 1,
                "query": queries[source_index],
                "similarity_to_selected_set_when_chosen": (
                    None
                    if similarity_when_selected[selected_index - 1] is None
                    else round(
                        similarity_when_selected[selected_index - 1], 6
                    )
                ),
                "nearest_selected_query_similarity": round(
                    float(nearest_similarities[selected_index - 1]), 6
                ),
            }
            for selected_index, source_index in enumerate(selected, start=1)
        ],
    }

    for path, payload in (
        (output_path, query_payload),
        (manifest_path, manifest),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    return manifest
