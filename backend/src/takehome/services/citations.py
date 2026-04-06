from __future__ import annotations

import re

from takehome.services.retrieval import ChunkResult


def parse_citations(
    response: str,
    chunks: list[ChunkResult],
) -> list[dict[str, str | int]]:
    """Extract [filename, page N] citations from LLM response text.

    Validates each citation against the chunks that were actually retrieved,
    deduplicates, and returns a list of citation dicts.
    """
    # Build lookup of valid (filename, page) -> document_id from chunks
    valid: dict[tuple[str, int], str] = {}
    for chunk in chunks:
        valid[(chunk.document_filename, chunk.page_number)] = chunk.document_id

    # Match patterns like [filename.pdf, page 3] or [filename.pdf, p. 3] or [filename.pdf, p 3]
    pattern = r"\[([^,\]]+),\s*(?:page|p\.?)\s*(\d+)\]"
    matches = re.findall(pattern, response, re.IGNORECASE)

    seen: set[tuple[str, int]] = set()
    citations: list[dict[str, str | int]] = []

    for filename_match, page_match in matches:
        filename = filename_match.strip()
        page = int(page_match)
        key = (filename, page)

        if key in seen:
            continue
        seen.add(key)

        # Try exact match first
        if key in valid:
            citations.append({
                "document_id": valid[key],
                "filename": filename,
                "page_number": page,
            })
        else:
            # Try case-insensitive match
            for (vf, vp), doc_id in valid.items():
                if vf.lower() == filename.lower() and vp == page:
                    citations.append({
                        "document_id": doc_id,
                        "filename": vf,  # use the canonical filename
                        "page_number": page,
                    })
                    break

    return citations


_RAW_CITATION_RE = re.compile(r"\[([^,\]]+),\s*(?:page|p\.?)\s*(\d+)\]", re.IGNORECASE)


def replace_citations_with_markers(
    text: str,
    citations: list[dict[str, str | int]],
) -> str:
    """Replace [filename, page N] with numbered markers [1], [2], etc.

    Numbers correspond to 1-based position in the citations list.
    Invalid citations (not in the list) are stripped.
    """
    # Build (filename_lower, page) -> 1-based index
    citation_index: dict[tuple[str, int], int] = {}
    for i, c in enumerate(citations):
        key = (str(c["filename"]).lower(), int(c["page_number"]))
        if key not in citation_index:
            citation_index[key] = i + 1

    def _replacer(match: re.Match[str]) -> str:
        filename = match.group(1).strip().lower()
        page = int(match.group(2))
        idx = citation_index.get((filename, page))
        if idx is not None:
            return f"[{idx}]"
        return ""

    result = _RAW_CITATION_RE.sub(_replacer, text)
    # Clean up: collapse double spaces, remove space before punctuation
    result = re.sub(r"  +", " ", result)
    result = re.sub(r" ([.,;:!?])", r"\1", result)
    return result.strip()
