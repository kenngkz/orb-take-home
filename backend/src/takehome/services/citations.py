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
