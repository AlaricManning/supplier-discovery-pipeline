"""Convert raw source documents into persisted parsed artifacts with Docling.

For each supported file in data/raw/ this writes four artifacts to data/parsed/,
named by the raw file's stem (the stable doc ID):

    {doc_id}.md           full document as markdown
    {doc_id}.json         lossless Docling document export
    {doc_id}.excerpt.md   Item 1 + Item 2 for 10-Ks, full text otherwise
    {doc_id}.meta.json    provenance: source path, docling version, parse time,
                          excerpt strategy

The parsed output is the pipeline's persisted source of truth; extraction and
embeddings are derived from it, so the meta records what produced it.

Usage:
    python -m supplier_discovery.ingestion.parse [--raw data/raw] [--out data/parsed]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from supplier_discovery.ingestion.sections import build_excerpt

SUPPORTED_SUFFIXES = {".html", ".htm", ".pdf", ".pptx"}


def build_converter():
    # Deferred import: docling pulls in its ML stack, which sections/edgar don't need.
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


def parse_file(raw_path: Path, out_dir: Path, converter) -> Path:
    """Convert one raw document; returns the markdown path."""
    doc_id = raw_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    document = converter.convert(raw_path).document

    markdown = document.export_to_markdown()
    md_path = out_dir / f"{doc_id}.md"
    md_path.write_text(markdown)

    with (out_dir / f"{doc_id}.json").open("w") as f:
        json.dump(document.export_to_dict(), f)

    excerpt, strategy = build_excerpt(markdown)
    (out_dir / f"{doc_id}.excerpt.md").write_text(excerpt)

    meta = {
        "doc_id": doc_id,
        "source_path": str(raw_path),
        "docling_version": version("docling"),
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "excerpt_strategy": strategy,
    }
    (out_dir / f"{doc_id}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return md_path


def run(raw_dir: Path, out_dir: Path, converter=None) -> list[Path]:
    sources = sorted(p for p in raw_dir.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES)
    if not sources:
        raise FileNotFoundError(f"no supported documents ({SUPPORTED_SUFFIXES}) in {raw_dir}")
    converter = converter or build_converter()
    parsed = []
    for raw_path in sources:
        parsed.append(parse_file(raw_path, out_dir, converter))
        print(f"parsed {raw_path.name} -> {parsed[-1]}")
    return parsed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("data/parsed"))
    args = parser.parse_args(argv)
    run(args.raw, args.out)


if __name__ == "__main__":
    main()
