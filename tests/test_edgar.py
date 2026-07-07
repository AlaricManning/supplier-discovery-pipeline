"""EDGAR client tests against a fake HTTP session — no network."""

import json

import pytest

from supplier_discovery.ingestion.edgar import COMPANIES, EdgarClient

SUBMISSIONS = {
    "name": "NUCOR CORP",
    "filings": {
        "recent": {
            # 10-K/A amendment and 10-Q must both be skipped in favor of the 10-K
            "form": ["10-Q", "10-K/A", "10-K", "10-K"],
            "accessionNumber": [
                "0000073309-26-000031",
                "0000073309-26-000020",
                "0000073309-26-000012",
                "0000073309-25-000012",
            ],
            "filingDate": ["2026-04-08", "2026-03-01", "2026-02-27", "2025-02-27"],
            "primaryDocument": ["nue-q1.htm", "nue-10ka.htm", "nue-10k.htm", "nue-10k-old.htm"],
        }
    },
}
FILING_HTML = b"<html><body>Item 1. Business</body></html>"


class FakeResponse:
    def __init__(self, *, body: bytes):
        self.content = body

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.requested = []

    def get(self, url, timeout):
        self.requested.append(url)
        if "data.sec.gov/submissions" in url:
            return FakeResponse(body=json.dumps(SUBMISSIONS).encode())
        return FakeResponse(body=FILING_HTML)


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def client(session):
    return EdgarClient(contact_email="test@example.com", session=session)


def test_requires_contact_email():
    with pytest.raises(ValueError, match="EDGAR_CONTACT_EMAIL"):
        EdgarClient(contact_email="")


def test_sets_sec_user_agent(client, session):
    assert session.headers["User-Agent"] == "supplier-discovery-pipeline test@example.com"


def test_latest_10k_skips_amendments_and_other_forms(client, session):
    filing = client.latest_10k("nucor")

    assert filing.form == "10-K"
    assert filing.accession_number == "0000073309-26-000012"
    assert filing.company_name == "NUCOR CORP"
    assert filing.cik == COMPANIES["nucor"]
    assert session.requested == ["https://data.sec.gov/submissions/CIK0000073309.json"]


def test_filing_document_url_strips_accession_dashes(client):
    filing = client.latest_10k("nucor")

    assert filing.url == (
        "https://www.sec.gov/Archives/edgar/data/73309/000007330926000012/nue-10k.htm"
    )


def test_no_10k_raises_lookup_error(client):
    SUBMISSIONS["filings"]["recent"]["form"] = ["10-Q", "10-K/A", "8-K", "8-K"]
    try:
        with pytest.raises(LookupError, match="nucor"):
            client.latest_10k("nucor")
    finally:
        SUBMISSIONS["filings"]["recent"]["form"] = ["10-Q", "10-K/A", "10-K", "10-K"]


def test_download_writes_html_and_provenance_sidecar(client, tmp_path):
    filing = client.latest_10k("nucor")
    html_path = client.download(filing, tmp_path)

    assert html_path == tmp_path / "nucor_10-K_0000073309-26-000012.html"
    assert html_path.read_bytes() == FILING_HTML

    meta = json.loads((tmp_path / "nucor_10-K_0000073309-26-000012.meta.json").read_text())
    assert meta["doc_id"] == "nucor_10-K_0000073309-26-000012"
    assert meta["url"] == filing.url
    assert meta["filing_date"] == "2026-02-27"
    assert meta["fetched_at"]
