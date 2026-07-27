import json

from finance_forensics.attachment_naming import rename_retrieved_attachments


def write_json(path, payload):
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_rename_retrieved_attachments_updates_files_and_manifests(tmp_path):
    catalog_path = tmp_path / "document_catalog.json"
    output_dir = tmp_path / "attachments_output"
    query_dir = output_dir / "query_001"
    files_dir = query_dir / "files"
    files_dir.mkdir(parents=True)

    catalog_record = {
        "document_id": "doc_1234567890abcdef",
        "source_filename": "001_source.pdf",
        "suggested_filename": "测试公司_年度报告_2025_doc_12345678.pdf",
    }
    result = {
        "rank": 1,
        "document_id": catalog_record["document_id"],
        "source_filename": catalog_record["source_filename"],
        "attachment_filename": "01__001_source.pdf",
        "suggested_filename": catalog_record["suggested_filename"],
    }
    write_json(catalog_path, [catalog_record])
    write_json(
        query_dir / "ranking.json",
        {"query_index": 1, "query": "测试", "results": [result.copy()]},
    )
    write_json(
        output_dir / "manifest.json",
        {"queries": [{"query_index": 1, "results": [result.copy()]}]},
    )
    (files_dir / "01__001_source.pdf").write_bytes(b"test content")

    stats = rename_retrieved_attachments(catalog_path, output_dir)

    expected_name = catalog_record["suggested_filename"]
    assert stats == {"total": 1, "renamed": 1, "unchanged": 0}
    assert not (files_dir / "01__001_source.pdf").exists()
    assert (files_dir / expected_name).read_bytes() == b"test content"
    ranking = json.loads((query_dir / "ranking.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (output_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert ranking["results"][0]["attachment_filename"] == expected_name
    assert manifest["queries"][0]["results"][0]["attachment_filename"] == expected_name

    second_stats = rename_retrieved_attachments(catalog_path, output_dir)
    assert second_stats == {"total": 1, "renamed": 0, "unchanged": 1}
