# supplier-discovery-pipeline

A data pipeline that ingests unstructured manufacturer documents (SEC 10-K excerpts, capability statements as PDF/PPTX), extracts structured supplier profiles with an LLM, normalizes them against a real taxonomy (NAICS, certifications), and supports hybrid supplier matching — hard filters on structured fields plus semantic vector similarity — against natural-language buyer requirements, with confidence-gated human review and a full audit trail back to source documents.

Domain: US steel manufacturers.

## How it works

1. **Ingestion** — [Docling](https://github.com/docling-project/docling) converts each source document (10-K HTML from SEC EDGAR, PDF and PPTX capability statements) into markdown plus lossless JSON, persisted to `data/parsed/`. This parsed output is the pipeline's source of truth: structured fields and embeddings are both derived views of it, regeneratable if the schema or embedding model changes.
2. **Extraction** — an LLM extracts a structured supplier profile (processes, products, certifications, locations, ...) from the parsed markdown against a Pydantic schema, with a confidence score per field. Missing information is `null`, never guessed. Audit metadata (source document ID, model version) is stamped by the pipeline, not produced by the LLM.
3. **Normalization** — extracted strings are matched against canonical taxonomies (NAICS codes, certification lists, US state codes) with deterministic fuzzy matching first; an LLM adjudicates only ambiguous mid-range cases, for auditability.
4. **Indexing** — the full parsed text (not the extracted JSON) is chunked and embedded into a vector index, preserving nuance the schema can't capture.
5. **Matching** — a natural-language buyer requirement is answered with hybrid search: hard filters on the normalized structured fields, vector similarity for fuzzy fit, and a weighted re-rank. Hard constraints never rely on vector similarity alone.
6. **Review** — low-confidence fields and matches are flagged for human review, with a full audit trail from every result back to its parsed document and original file.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in keys; never committed
```

## Fetching source documents

```bash
python -m supplier_discovery.ingestion.edgar                    # Nucor, Steel Dynamics, Cleveland-Cliffs
python -m supplier_discovery.ingestion.edgar --companies us-steel commercial-metals worthington
```

Downloads each company's latest 10-K from the official SEC EDGAR API as original HTML into `data/raw/`, with a `.meta.json` provenance sidecar (CIK, accession number, source URL, fetch time) per filing. Requires `EDGAR_CONTACT_EMAIL` in `.env` — the SEC requires a User-Agent header identifying the requester.

## Parsing documents

```bash
python -m supplier_discovery.ingestion.parse   # data/raw/ -> data/parsed/
```

Converts every supported document in `data/raw/` (HTML, PDF, PPTX) with [Docling](https://github.com/docling-project/docling) into four persisted artifacts per doc in `data/parsed/`: full markdown, lossless Docling JSON, an excerpt (Item 1 Business + Item 2 Properties for 10-Ks; full text for anything else), and a `.meta.json` recording provenance, Docling version, and which excerpt strategy applied.

## Development

```bash
ruff check .
pytest
```

## Layout

```
src/supplier_discovery/
  ingestion/        # Docling conversion (raw docs -> persisted parsed artifacts)
  extraction/       # LLM extraction + Pydantic schema, per-field confidence
  normalization/    # taxonomy + rapidfuzz matching, LLM fallback for ambiguous cases
  indexing/         # chunking + embeddings + vector index
  matching/         # hybrid query/ranking logic
data/
  raw/              # original source docs (gitignored)
  parsed/           # persisted Docling output (gitignored)
  extracted/        # LLM extraction output (gitignored)
  taxonomy/         # NAICS csv, certifications list (committed)
```
