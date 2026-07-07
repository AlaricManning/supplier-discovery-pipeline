"""Fetch the latest 10-K filing for steel manufacturers from SEC EDGAR.

Uses the official submissions API (data.sec.gov) and saves the original
filing HTML into data/raw/, one file per company, plus a .meta.json sidecar
recording provenance (CIK, accession number, source URL, fetch time) for the
audit trail. Section extraction (Item 1/Item 2) happens downstream, on the
Docling-parsed markdown — not here.

Usage:
    python -m supplier_discovery.ingestion.edgar [--companies nucor us-steel] [--out data/raw]

Requires EDGAR_CONTACT_EMAIL in the environment (or .env): the SEC requires
a User-Agent header declaring who is making requests.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
DOCUMENT_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{document}"

# SEC allows at most 10 req/s; stay well under.
MIN_REQUEST_INTERVAL_S = 0.15

COMPANIES: dict[str, int] = {
    "nucor": 73309,
    "steel-dynamics": 1022671,
    "cleveland-cliffs": 764065,
    "us-steel": 1163302,
    "commercial-metals": 22444,
    "worthington": 108516,
}
DEFAULT_COMPANIES = ["nucor", "steel-dynamics", "cleveland-cliffs"]


@dataclass
class Filing:
    slug: str
    cik: int
    company_name: str
    form: str
    accession_number: str
    filing_date: str
    primary_document: str
    url: str

    @property
    def doc_id(self) -> str:
        return f"{self.slug}_10-K_{self.accession_number}"


class EdgarClient:
    def __init__(self, contact_email: str, session: requests.Session | None = None):
        if not contact_email:
            raise ValueError(
                "EDGAR_CONTACT_EMAIL is required: the SEC mandates a User-Agent "
                "header with contact details (see .env.example)"
            )
        self._session = session or requests.Session()
        self._session.headers["User-Agent"] = f"supplier-discovery-pipeline {contact_email}"
        self._last_request_at = 0.0

    def _get(self, url: str) -> requests.Response:
        wait = MIN_REQUEST_INTERVAL_S - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        response = self._session.get(url, timeout=30)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response

    def latest_10k(self, slug: str) -> Filing:
        """Find the most recent 10-K (not 10-K/A amendments) for a known company."""
        cik = COMPANIES[slug]
        submissions = self._get(SUBMISSIONS_URL.format(cik=cik)).json()
        recent = submissions["filings"]["recent"]
        for form, accession, filed, document in zip(
            recent["form"],
            recent["accessionNumber"],
            recent["filingDate"],
            recent["primaryDocument"],
            strict=True,
        ):
            if form == "10-K":
                return Filing(
                    slug=slug,
                    cik=cik,
                    company_name=submissions["name"],
                    form=form,
                    accession_number=accession,
                    filing_date=filed,
                    primary_document=document,
                    url=DOCUMENT_URL.format(
                        cik=cik,
                        accession_nodash=accession.replace("-", ""),
                        document=document,
                    ),
                )
        raise LookupError(f"no 10-K in recent EDGAR submissions for {slug} (CIK {cik})")

    def download(self, filing: Filing, out_dir: Path) -> Path:
        """Save the original filing HTML plus a .meta.json provenance sidecar."""
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / f"{filing.doc_id}.html"
        html_path.write_bytes(self._get(filing.url).content)

        meta = asdict(filing) | {
            "doc_id": filing.doc_id,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = out_dir / f"{filing.doc_id}.meta.json"
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        return html_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--companies",
        nargs="+",
        choices=sorted(COMPANIES),
        default=DEFAULT_COMPANIES,
        help=f"company slugs to fetch (default: {' '.join(DEFAULT_COMPANIES)})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/raw"),
        help="output directory (default: data/raw)",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    client = EdgarClient(contact_email=os.environ.get("EDGAR_CONTACT_EMAIL", ""))
    for slug in args.companies:
        filing = client.latest_10k(slug)
        path = client.download(filing, args.out)
        print(f"{filing.company_name}: 10-K filed {filing.filing_date} -> {path}")


if __name__ == "__main__":
    main()
