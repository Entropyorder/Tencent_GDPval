import json
from pathlib import Path

from .retrieval import catalog_attachment_filename


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path, payload):
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def rename_retrieved_attachments(catalog_path, output_dir):
    catalog_path = Path(catalog_path).resolve()
    output_dir = Path(output_dir).resolve()
    catalog = _load_json(catalog_path)
    records_by_source = {
        record["source_filename"]: record
        for record in catalog
        if record.get("source_filename")
    }

    changed = 0
    total = 0
    attachment_names = {}
    ranking_paths = sorted(output_dir.glob("query_*/ranking.json"))
    if not ranking_paths:
        raise FileNotFoundError(f"no query ranking files found under: {output_dir}")

    for ranking_path in ranking_paths:
        ranking = _load_json(ranking_path)
        query_index = int(ranking["query_index"])
        files_dir = ranking_path.parent / "files"
        used_names = set()

        for result in ranking.get("results", []):
            source_filename = result["source_filename"]
            record = records_by_source.get(source_filename)
            if record is None:
                raise KeyError(f"source file is missing from catalog: {source_filename}")

            old_name = result["attachment_filename"]
            new_name = catalog_attachment_filename(record, used_names)
            used_names.add(new_name)
            old_path = files_dir / old_name
            new_path = files_dir / new_name

            if old_name != new_name:
                if not old_path.is_file():
                    raise FileNotFoundError(f"retrieved attachment is missing: {old_path}")
                if new_path.exists():
                    raise FileExistsError(f"catalog filename already exists: {new_path}")
                old_path.rename(new_path)
                changed += 1
            elif not new_path.is_file():
                raise FileNotFoundError(f"retrieved attachment is missing: {new_path}")

            result["attachment_filename"] = new_name
            result["suggested_filename"] = record.get("suggested_filename")
            attachment_names[(query_index, result["document_id"])] = new_name
            total += 1

        _write_json(ranking_path, ranking)

    manifest_path = output_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = _load_json(manifest_path)
        for query in manifest.get("queries", []):
            query_index = int(query["query_index"])
            for result in query.get("results", []):
                key = (query_index, result["document_id"])
                if key not in attachment_names:
                    raise KeyError(
                        "manifest result is missing from ranking files: "
                        f"query={query_index} document={result['document_id']}"
                    )
                result["attachment_filename"] = attachment_names[key]
                record = records_by_source[result["source_filename"]]
                result["suggested_filename"] = record.get("suggested_filename")
        _write_json(manifest_path, manifest)

    return {"total": total, "renamed": changed, "unchanged": total - changed}
