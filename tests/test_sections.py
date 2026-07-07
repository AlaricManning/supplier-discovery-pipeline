"""Item section extraction from 10-K-style markdown."""

from supplier_discovery.ingestion.sections import build_excerpt, extract_item

BUSINESS = "We operate electric arc furnace steel mills across the United States. " * 30
RISK = "Steel prices are cyclical and volatile which may affect our results. " * 30
PROPERTIES = "Our principal facilities include mills in Indiana and Ohio. " * 30
LEGAL = "We are involved in various legal proceedings from time to time. " * 30

TEN_K = f"""# ACME STEEL CORP FORM 10-K

Table of contents

Item 1. Business

Item 1A. Risk Factors

Item 2. Properties

Item 3. Legal Proceedings

Part I

## Item 1. Business

{BUSINESS}

## ITEM 1A - RISK FACTORS

{RISK}

**Item 2. Properties**

{PROPERTIES}

## Item 3. Legal Proceedings

{LEGAL}
"""


def test_extract_item_skips_table_of_contents_entries():
    section = extract_item(TEN_K, "1")

    assert section is not None
    assert section.startswith("## Item 1. Business")
    assert "electric arc furnace" in section
    assert "cyclical" not in section  # stops at Item 1A


def test_extract_item_1_does_not_match_1a():
    section = extract_item(TEN_K, "1")
    assert "RISK FACTORS" not in section


def test_extract_item_handles_bold_headings_and_stops_at_next_item():
    section = extract_item(TEN_K, "2")

    assert section.startswith("**Item 2. Properties**")
    assert "Indiana" in section
    assert "legal proceedings" not in section.lower()


def test_extract_item_returns_none_below_minimum_length():
    toc_only = "Item 1. Business\n\nItem 2. Properties\n\nshort body"
    assert extract_item(toc_only, "1") is None


def test_build_excerpt_concatenates_items_1_and_2():
    excerpt, strategy = build_excerpt(TEN_K)

    assert strategy == "10k-items"
    assert "electric arc furnace" in excerpt
    assert "Indiana" in excerpt
    assert "cyclical" not in excerpt
    assert "legal proceedings" not in excerpt.lower()


def test_extract_item_matches_single_value_table_row_headings():
    # Cleveland-Cliffs style: body headings are one-row tables repeating a
    # single value; TOC rows have distinct cells (number, title, page link).
    ten_k = f"""# CLIFFS FORM 10-K

| ITEM 1. | BUSINESS | [4](#toc-link) |
| ITEM 1A. | RISK FACTORS | [17](#toc-link) |
| ITEM 2. | PROPERTIES | [30](#toc-link) |

| ITEM 1. BUSINESS | ITEM 1. BUSINESS | ITEM 1. BUSINESS |
|----|----|----|

{BUSINESS}

| ITEM 1A. RISK FACTORS | ITEM 1A. RISK FACTORS | ITEM 1A. RISK FACTORS |

{RISK}

| ITEM 2. PROPERTIES | ITEM 2. PROPERTIES | ITEM 2. PROPERTIES |

{PROPERTIES}

| ITEM 3. LEGAL PROCEEDINGS | ITEM 3. LEGAL PROCEEDINGS | ITEM 3. LEGAL PROCEEDINGS |

{LEGAL}
"""
    excerpt, strategy = build_excerpt(ten_k)

    assert strategy == "10k-items"
    assert "electric arc furnace" in excerpt
    assert "Indiana" in excerpt
    assert "cyclical" not in excerpt
    assert "legal proceedings" not in excerpt.lower()


def test_item_number_word_boundary_ignores_regulation_references():
    body = "Item 1300 of Regulation S-K defines a qualified person. " * 30
    assert extract_item(f"Item 1300 of Regulation S-K\n\n{body}", "13") is None


def test_build_excerpt_falls_back_to_full_document():
    capability_statement = "We are a family-owned galvanizing shop. " * 100
    excerpt, strategy = build_excerpt(capability_statement)

    assert strategy == "full-document"
    assert excerpt == capability_statement
