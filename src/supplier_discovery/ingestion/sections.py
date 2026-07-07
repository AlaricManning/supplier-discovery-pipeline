"""Extract 10-K item sections (Item 1 Business, Item 2 Properties) from parsed markdown.

Filers format item headings inconsistently: "Item 1. Business", "ITEM 1 -
BUSINESS", bold, varying heading levels, and some (e.g. Cleveland-Cliffs)
render each heading as a single-row table, which is also how tables of
contents appear. Strategy: collect every line that plausibly is an item
heading — plain lines matching the heading pattern, plus table rows whose
cells all repeat one heading-shaped value (TOC rows have several distinct
cells: number, title, page link) — then for the requested item keep the
candidate spanning the most text before the next heading. TOC hits produce
near-empty spans, so the document body wins naturally; spans below
MIN_SECTION_CHARS are treated as not found.
"""

from __future__ import annotations

import re

# One heading on one line: optional markdown heading/emphasis markers, "Item",
# a 1-2 digit number with optional letter, a separator, then the title. The
# \b after the number keeps "Item 1300 of Regulation S-K" from matching.
ITEM_HEADING = re.compile(
    r"[#*_ \t]*item\s+(?P<num>\d{1,2}[a-c]?)\b\s*[.:–—-]?[*_ \t]*(?P<title>[^|\n]*)",
    re.IGNORECASE,
)

MIN_SECTION_CHARS = 1000


def _heading_item_number(line: str) -> str | None:
    """The item number if this line is a section heading, else None."""
    stripped = line.strip()
    if stripped.startswith("|"):
        cells = {c.strip() for c in stripped.strip("|").split("|")}
        cells -= {""}
        if len(cells) != 1 or any(set(c) <= {"-", ":", " "} for c in cells):
            return None  # TOC row, data row, or |---| separator
        stripped = cells.pop()
    match = ITEM_HEADING.fullmatch(stripped)
    return match.group("num").lower() if match else None


def _headings(markdown: str) -> list[tuple[int, str]]:
    """(character offset, item number) for every heading line, in order."""
    found = []
    offset = 0
    for line in markdown.splitlines(keepends=True):
        num = _heading_item_number(line)
        if num is not None:
            found.append((offset, num))
        offset += len(line)
    return found


def extract_item(markdown: str, item: str) -> str | None:
    """Return the text of one item section (e.g. item="1" or "1a"), or None."""
    headings = _headings(markdown)
    best: str | None = None
    for i, (start, num) in enumerate(headings):
        if num != item.lower():
            continue
        end = headings[i + 1][0] if i + 1 < len(headings) else len(markdown)
        candidate = markdown[start:end].strip()
        if best is None or len(candidate) > len(best):
            best = candidate
    if best is not None and len(best) < MIN_SECTION_CHARS:
        return None
    return best


def build_excerpt(markdown: str) -> tuple[str, str]:
    """Return (excerpt, strategy) for downstream extraction and embedding.

    10-Ks reduce to Item 1 (Business) + Item 2 (Properties) — the sections that
    describe capabilities — leaving out financial statements and risk-factor
    boilerplate. Anything without a recognizable Item 1 (capability statements,
    synthetic profiles) passes through whole.
    """
    item1 = extract_item(markdown, "1")
    if item1 is None:
        return markdown, "full-document"
    item2 = extract_item(markdown, "2")
    sections = [item1] if item2 is None else [item1, item2]
    return "\n\n".join(sections), "10k-items"
