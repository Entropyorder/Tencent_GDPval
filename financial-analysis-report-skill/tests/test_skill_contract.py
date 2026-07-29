from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_has_valid_frontmatter_and_execution_contract():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: generating-financial-analysis-reports" in text
    assert "description: Use when" in text
    for required in [
        "python scripts/render_report.py",
        "python scripts/validate_report.py",
        "黑色三线表",
        "首行缩进",
        "Times New Roman",
        "references/financial_writing_guide.md",
        "internal/validation_report.json",
    ]:
        assert required in text


def test_package_references_and_style_contract_exist():
    for relative in [
        "README.md",
        "references/format_spec.md",
        "references/financial_writing_guide.md",
        "style/report_style.yaml",
    ]:
        assert (ROOT / relative).exists(), relative
