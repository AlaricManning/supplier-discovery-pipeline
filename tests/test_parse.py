"""Docling runner orchestration, with the converter stubbed out."""

import json
from types import SimpleNamespace

import pytest

from supplier_discovery.ingestion.parse import parse_file, run
from tests.test_sections import TEN_K


class FakeDocument:
    def export_to_markdown(self):
        return TEN_K

    def export_to_dict(self):
        return {"schema_name": "DoclingDocument", "texts": ["stub"]}


class FakeConverter:
    def __init__(self):
        self.converted = []

    def convert(self, path):
        self.converted.append(path)
        return SimpleNamespace(document=FakeDocument())


@pytest.fixture
def raw_dir(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "acme_10-K_0000000000-26-000001.html").write_text("<html>stub</html>")
    (raw / "acme_10-K_0000000000-26-000001.meta.json").write_text("{}")
    return raw


def test_parse_file_writes_all_four_artifacts(raw_dir, tmp_path):
    out = tmp_path / "parsed"
    md_path = parse_file(
        raw_dir / "acme_10-K_0000000000-26-000001.html", out, FakeConverter()
    )

    doc_id = "acme_10-K_0000000000-26-000001"
    assert md_path == out / f"{doc_id}.md"
    assert md_path.read_text() == TEN_K
    assert json.loads((out / f"{doc_id}.json").read_text())["schema_name"] == "DoclingDocument"

    excerpt = (out / f"{doc_id}.excerpt.md").read_text()
    assert "electric arc furnace" in excerpt
    assert "legal proceedings" not in excerpt.lower()

    meta = json.loads((out / f"{doc_id}.meta.json").read_text())
    assert meta["doc_id"] == doc_id
    assert meta["excerpt_strategy"] == "10k-items"
    assert meta["docling_version"]
    assert meta["source_path"].endswith(f"{doc_id}.html")


def test_run_converts_supported_files_only(raw_dir, tmp_path):
    converter = FakeConverter()
    parsed = run(raw_dir, tmp_path / "parsed", converter)

    assert len(parsed) == 1  # .meta.json sidecar is not a source document
    assert converter.converted == [raw_dir / "acme_10-K_0000000000-26-000001.html"]


def test_run_with_no_documents_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="no supported documents"):
        run(empty, tmp_path / "parsed", FakeConverter())
