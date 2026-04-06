"""Integration tests for retrieval quality against realistic CRE lawyer queries.

These tests evaluate whether PostgreSQL full-text search retrieves the right
document chunks for the kinds of questions commercial real estate lawyers
actually ask during due diligence.

Each test seeds realistic legal document chunks, runs a query through
`retrieve_chunks`, and asserts on which chunks are/aren't returned.

Where keyword-based FTS is structurally unable to match (synonym gaps,
conceptual queries), the test documents that expectation and verifies the
fallback path activates correctly.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from takehome.db.models import Conversation, Document, DocumentChunk
from takehome.services.retrieval import ChunkResult, retrieve_chunks


async def _seed_chunks(
    session: AsyncSession,
    chunks: list[tuple[str, int, str]],
) -> str:
    """Create a conversation with documents and chunks.

    Each chunk tuple is (filename, page_number, content).
    Returns the conversation ID.
    """
    conv = Conversation(title="CRE Due Diligence")
    session.add(conv)
    await session.flush()

    doc_map: dict[str, Document] = {}
    for fname in sorted({c[0] for c in chunks}):
        doc = Document(
            conversation_id=conv.id,
            filename=fname,
            file_path=f"/tmp/{fname}",
            extracted_text="",
            page_count=sum(1 for c in chunks if c[0] == fname),
        )
        session.add(doc)
        await session.flush()
        doc_map[fname] = doc

    for fname, page_num, content in chunks:
        chunk = DocumentChunk(
            document_id=doc_map[fname].id,
            page_number=page_num,
            content=content,
        )
        session.add(chunk)

    await session.commit()
    return conv.id


def _matched_keys(results: list[ChunkResult]) -> set[tuple[str, int]]:
    """Return set of (filename, page_number) from results for easy assertion."""
    return {(r.document_filename, r.page_number) for r in results}


def _top_n_keys(results: list[ChunkResult], n: int) -> set[tuple[str, int]]:
    """Return set of (filename, page_number) from the top n ranked results."""
    return {(r.document_filename, r.page_number) for r in results[:n]}


def _is_fts_path(results: list[ChunkResult]) -> bool:
    """True if results came from FTS (any result has rank > 0), not fallback."""
    return any(r.rank > 0.0 for r in results)


# ---------------------------------------------------------------------------
# 1. Simple factual lookup
# ---------------------------------------------------------------------------


async def test_simple_rent_lookup(session: AsyncSession) -> None:
    """Lawyer asks 'what is the rent?' — should retrieve the rent clause page."""
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of One Hundred and "
                "Seventy-Five Thousand Pounds (£175,000) per annum exclusive of "
                "VAT, payable quarterly in advance on the usual quarter days. The "
                "first payment of rent shall be made on the date of this Lease.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                7,
                "The Tenant shall not assign, underlet, charge or part with "
                "possession of the whole or any part of the Premises without the "
                "prior written consent of the Landlord, such consent not to be "
                "unreasonably withheld or delayed.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                12,
                "The Tenant shall keep the Premises in good and substantial "
                "repair and condition throughout the Term and shall yield up the "
                "Premises at the expiry of the Term in such repair and condition.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                15,
                "The Landlord hereby insures the Building against loss or damage "
                "by the Insured Risks and the Tenant shall pay to the Landlord "
                "a fair proportion of the insurance premium.",
            ),
        ],
    )

    results = await retrieve_chunks(session, conv_id, "what is the rent", min_results=1)

    matched = _matched_keys(results)
    assert ("lease-100-bishopsgate.pdf", 3) in matched
    assert _is_fts_path(results)
    # Rent clause should rank in top 2 (precision, not just recall)
    assert ("lease-100-bishopsgate.pdf", 3) in _top_n_keys(results, 2)
    # Assignment clause, repair clause, and insurance clause should not match
    assert ("lease-100-bishopsgate.pdf", 7) not in matched
    assert ("lease-100-bishopsgate.pdf", 12) not in matched


# ---------------------------------------------------------------------------
# 2. Cross-document comparison
# ---------------------------------------------------------------------------


async def test_cross_document_rent_comparison(session: AsyncSession) -> None:
    """Lawyer compares rent terms across a lease and a rent review memorandum."""
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                3,
                "The Tenant shall pay to the Landlord an initial annual rent of "
                "One Hundred and Fifty Thousand Pounds (£150,000) per annum "
                "exclusive of VAT. Rent shall be payable quarterly in advance "
                "on the usual quarter days.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                8,
                "The Tenant covenants to use the Premises solely for purposes "
                "falling within Class E of the Town and Country Planning (Use "
                "Classes) Order 1987 as amended.",
            ),
            (
                "rent-review-memo-2023.pdf",
                1,
                "MEMORANDUM OF RENT REVIEW dated 15 March 2023. Pursuant to "
                "clause 4.2 of the Lease dated 1 June 2018, the revised rent "
                "payable from the review date of 1 June 2023 shall be One "
                "Hundred and Seventy-Five Thousand Pounds (£175,000) per annum.",
            ),
            (
                "rent-review-memo-2023.pdf",
                2,
                "The parties agree that the revised rent was determined by "
                "reference to the open market rental value of comparable "
                "premises in the City of London as at the review date.",
            ),
        ],
    )

    results = await retrieve_chunks(session, conv_id, "rent", min_results=1)

    matched = _matched_keys(results)
    # Both documents' rent-related pages should be retrieved
    assert ("lease-100-bishopsgate.pdf", 3) in matched
    assert ("rent-review-memo-2023.pdf", 1) in matched
    # Both rent pages should rank in top 3 (precision)
    top3 = _top_n_keys(results, 3)
    assert ("lease-100-bishopsgate.pdf", 3) in top3
    assert ("rent-review-memo-2023.pdf", 1) in top3
    # The use clause should not match
    assert ("lease-100-bishopsgate.pdf", 8) not in matched
    # Results should span both documents
    doc_names = {r.document_filename for r in results}
    assert len(doc_names) == 2


# ---------------------------------------------------------------------------
# 3. Legal concept search — exact terminology
# ---------------------------------------------------------------------------


async def test_break_clause_search(session: AsyncSession) -> None:
    """Lawyer searches for 'break clause' — should match the exact legal term."""
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-50-cheapside.pdf",
                5,
                "The Tenant shall have the right to determine this Lease by "
                "serving not less than six months' prior written notice on the "
                "Landlord (a 'break notice') to expire on the fifth anniversary "
                "of the Term Commencement Date (the 'break date'). This break "
                "clause is conditional upon the Tenant having paid all rent and "
                "other sums due under this Lease.",
            ),
            (
                "lease-50-cheapside.pdf",
                6,
                "Any break notice served by the Tenant pursuant to clause 8.1 "
                "shall be irrevocable and time shall be of the essence in "
                "respect of the conditions to be satisfied on the break date.",
            ),
            (
                "lease-50-cheapside.pdf",
                10,
                "The Tenant shall not make any structural alterations to the "
                "Premises without the prior written consent of the Landlord. "
                "Non-structural alterations may be carried out with the "
                "Landlord's prior written consent, not to be unreasonably "
                "withheld.",
            ),
        ],
    )

    results = await retrieve_chunks(session, conv_id, "break clause", min_results=1)

    matched = _matched_keys(results)
    assert ("lease-50-cheapside.pdf", 5) in matched
    assert ("lease-50-cheapside.pdf", 6) in matched
    assert _is_fts_path(results)
    # Break clause pages should rank in top 2 (precision)
    top2 = _top_n_keys(results, 2)
    assert ("lease-50-cheapside.pdf", 5) in top2
    assert ("lease-50-cheapside.pdf", 6) in top2
    # Alterations clause should not match
    assert ("lease-50-cheapside.pdf", 10) not in matched


# ---------------------------------------------------------------------------
# 4. Synonym / related term mismatch — FTS expected to fail
# ---------------------------------------------------------------------------


async def test_termination_synonym_for_break_clause(session: AsyncSession) -> None:
    """Lawyer searches 'termination rights' but document uses 'break clause'.

    PostgreSQL FTS with the English stemmer does not treat 'termination' and
    'break clause' as synonyms. This test documents that FTS will miss the
    match and verifies the fallback path activates, returning all chunks so
    the LLM can reason over the full context.
    """
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-50-cheapside.pdf",
                5,
                "The Tenant shall have the right to determine this Lease by "
                "serving not less than six months' prior written notice on the "
                "Landlord (a 'break notice') to expire on the fifth anniversary "
                "of the Term Commencement Date (the 'break date'). This break "
                "clause is conditional upon the Tenant having paid all rent.",
            ),
            (
                "lease-50-cheapside.pdf",
                9,
                "Upon expiry or sooner determination of the Term the Tenant "
                "shall yield up the Premises with vacant possession in repair "
                "and condition consistent with the Tenant's covenants herein.",
            ),
        ],
    )

    results = await retrieve_chunks(session, conv_id, "termination rights")

    # FTS will not match 'termination' to 'break clause' — expect fallback
    # Note: 'determination' (page 5 and 9) stems to 'determin' in English config,
    # while 'termination' stems to 'termin'. These are different stems, so no FTS
    # match. Fallback returns all chunks.
    assert not _is_fts_path(results)
    assert len(results) == 2


async def test_dilapidations_synonym_for_repair(session: AsyncSession) -> None:
    """Lawyer searches 'dilapidations' but document uses 'repair obligations'.

    'Dilapidations' is standard UK CRE jargon for the liability arising from
    breach of repair covenants. FTS won't link it to 'repair' since they share
    no stem. Fallback expected.
    """
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                12,
                "The Tenant shall keep the interior of the Premises and the "
                "Tenant's fixtures and fittings in good and substantial repair "
                "and condition throughout the Term and shall yield up the "
                "Premises at the expiry of the Term in such repair and "
                "condition. The Tenant shall be responsible for all works of "
                "repair and maintenance to the interior of the Premises.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                13,
                "The Landlord covenants to keep the structure and exterior of "
                "the Building including the roof, foundations, and main walls "
                "in good and substantial repair.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of One Hundred "
                "and Seventy-Five Thousand Pounds per annum exclusive of VAT.",
            ),
        ],
    )

    results = await retrieve_chunks(session, conv_id, "dilapidations liability")

    # 'dilapidations' won't match 'repair' via FTS — fallback expected
    assert not _is_fts_path(results)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# 5. Multi-term query
# ---------------------------------------------------------------------------


async def test_rent_review_two_term_query(session: AsyncSession) -> None:
    """Lawyer asks about the 'rent review' — FTS should match pages with both terms."""
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                4,
                "The rent payable under this Lease shall be reviewed on each "
                "Review Date. The revised rent shall be the higher of the rent "
                "payable immediately before the relevant Review Date and the "
                "open market rent as agreed or determined in accordance with "
                "the provisions of Schedule 3.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                5,
                "Schedule 3: Rent Review. 1. The open market rent shall be "
                "determined by a surveyor acting as an independent expert "
                "appointed by agreement between the parties or, in default of "
                "agreement, by the President of the Royal Institution of "
                "Chartered Surveyors. The surveyor shall have regard to "
                "comparable market evidence.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of One Hundred "
                "and Seventy-Five Thousand Pounds per annum exclusive of VAT.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                10,
                "The Tenant shall not make any structural alterations to the "
                "Premises without the prior written consent of the Landlord.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "rent review", min_results=1
    )

    matched = _matched_keys(results)
    # Pages 4 and 5 both contain 'rent' AND 'review' — should match via FTS
    assert ("lease-100-bishopsgate.pdf", 4) in matched
    assert ("lease-100-bishopsgate.pdf", 5) in matched
    assert _is_fts_path(results)
    # Rent review pages should rank in top 3 (precision)
    top3 = _top_n_keys(results, 3)
    assert ("lease-100-bishopsgate.pdf", 4) in top3
    assert ("lease-100-bishopsgate.pdf", 5) in top3
    # Page 3 has 'rent' but not 'review', and websearch_to_tsquery ANDs terms
    assert ("lease-100-bishopsgate.pdf", 3) not in matched
    # The alterations clause should not match
    assert ("lease-100-bishopsgate.pdf", 10) not in matched


async def test_rent_review_mechanism_fts_limitation(session: AsyncSession) -> None:
    """Adding 'mechanism' to 'rent review' breaks FTS due to AND semantics.

    websearch_to_tsquery('english', 'rent review mechanism') produces
    'rent' & 'review' & 'mechan'. No chunk contains the word 'mechanism',
    so the AND query matches nothing. This is a known limitation of
    websearch_to_tsquery: every query term must appear in the chunk. Fallback
    correctly provides all chunks for the LLM to reason over.
    """
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                4,
                "The rent payable under this Lease shall be reviewed on each "
                "Review Date. The revised rent shall be the higher of the rent "
                "payable immediately before the relevant Review Date and the "
                "open market rent as agreed or determined in accordance with "
                "the provisions of Schedule 3.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                5,
                "Schedule 3: Rent Review. 1. The open market rent shall be "
                "determined by a surveyor acting as an independent expert "
                "appointed by agreement between the parties or, in default of "
                "agreement, by the President of the Royal Institution of "
                "Chartered Surveyors.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                10,
                "The Tenant shall not make any structural alterations to the "
                "Premises without the prior written consent of the Landlord.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "rent review mechanism", min_results=1
    )

    # FTS fails: 'mechan' stem not in any chunk -> zero hits -> fallback
    assert not _is_fts_path(results)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# 6. Query matching multiple documents
# ---------------------------------------------------------------------------


async def test_insurance_across_documents(session: AsyncSession) -> None:
    """Lawyer searches 'insurance' across a lease and licence to alter."""
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                15,
                "The Landlord shall insure the Building against loss or damage "
                "by fire, storm, flood, and such other risks as the Landlord "
                "considers appropriate. The Tenant shall pay to the Landlord "
                "a fair proportion of the insurance premium by way of additional "
                "rent.",
            ),
            (
                "licence-to-alter.pdf",
                3,
                "The Tenant shall prior to commencement of the Works effect "
                "and maintain a policy of insurance in respect of public "
                "liability and employer's liability in a sum not less than Five "
                "Million Pounds (£5,000,000) for any one occurrence and shall "
                "produce evidence of such insurance to the Landlord on demand.",
            ),
            (
                "licence-to-alter.pdf",
                2,
                "The Landlord hereby grants licence to the Tenant to carry out "
                "the Works described in the attached specification at the "
                "Premises in accordance with the plans approved by the Landlord.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                7,
                "The Tenant shall not assign, underlet, charge or part with "
                "possession of the whole or any part of the Premises.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "insurance", min_results=1
    )

    matched = _matched_keys(results)
    # Both insurance-related pages should match across documents
    assert ("lease-100-bishopsgate.pdf", 15) in matched
    assert ("licence-to-alter.pdf", 3) in matched
    assert _is_fts_path(results)
    # Insurance pages should rank in top 2 (precision)
    top2 = _top_n_keys(results, 2)
    assert ("lease-100-bishopsgate.pdf", 15) in top2
    assert ("licence-to-alter.pdf", 3) in top2
    # Non-insurance pages should not match
    assert ("lease-100-bishopsgate.pdf", 7) not in matched
    assert ("licence-to-alter.pdf", 2) not in matched


async def test_insurance_obligations_and_limitation(session: AsyncSession) -> None:
    """'Insurance obligations' fails FTS because of AND semantics.

    websearch_to_tsquery('english', 'insurance obligations') -> 'insur' & 'oblig'.
    The legal text says 'insure' and 'insurance' but never 'obligation' or
    'obligations'. Since websearch_to_tsquery requires ALL terms to match, no
    chunk qualifies. This is a real FTS gap: lawyers naturally say 'insurance
    obligations' but legal drafters write 'the Tenant shall insure' without
    using the word 'obligation'. Fallback is the correct outcome here.
    """
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                15,
                "The Landlord shall insure the Building against loss or damage "
                "by fire, storm, flood, and such other risks as the Landlord "
                "considers appropriate. The Tenant shall pay to the Landlord "
                "a fair proportion of the insurance premium by way of additional "
                "rent.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                7,
                "The Tenant shall not assign, underlet, charge or part with "
                "possession of the whole or any part of the Premises.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "insurance obligations"
    )

    # 'oblig' stem not in any chunk -> FTS misses -> fallback
    assert not _is_fts_path(results)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# 7. No matching chunks — graceful fallback
# ---------------------------------------------------------------------------


async def test_no_match_falls_back_to_all_chunks(session: AsyncSession) -> None:
    """Query about a topic not present in any document triggers full fallback."""
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of One Hundred "
                "and Seventy-Five Thousand Pounds per annum exclusive of VAT.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                7,
                "The Tenant shall not assign, underlet, charge or part with "
                "possession of the whole or any part of the Premises.",
            ),
            (
                "title-register.pdf",
                1,
                "Title Number: NGL123456. This register describes the land and "
                "estate comprised in the title. The registered proprietor is "
                "Bishopsgate Property Holdings Limited.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "environmental contamination survey"
    )

    # No chunk contains environmental/contamination/survey — full fallback
    assert not _is_fts_path(results)
    assert len(results) == 3
    # Fallback should return in reading order
    assert results[0].page_number <= results[1].page_number or (
        results[0].document_filename < results[1].document_filename
    )


# ---------------------------------------------------------------------------
# 8. Broad / vague query — expected fallback
# ---------------------------------------------------------------------------


async def test_broad_summary_query_triggers_fallback(session: AsyncSession) -> None:
    """'Summarise the key terms' is too vague for FTS — fallback expected.

    The word 'summarise' doesn't appear in any legal document, and 'key' and
    'terms' are extremely generic. FTS will either match nothing or match too
    few chunks to meet min_results, correctly falling back to full context
    so the LLM can produce a genuine summary.
    """
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-50-cheapside.pdf",
                1,
                "THIS LEASE is made on the 1st day of January 2020 BETWEEN "
                "(1) Cheapside Investments Limited (the 'Landlord') and "
                "(2) TechCo Services Limited (the 'Tenant').",
            ),
            (
                "lease-50-cheapside.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of Eighty "
                "Thousand Pounds (£80,000) per annum exclusive of VAT.",
            ),
            (
                "lease-50-cheapside.pdf",
                5,
                "The Tenant shall have the right to determine this Lease by "
                "serving not less than six months' prior written notice on the "
                "Landlord to expire on the fifth anniversary of the Term "
                "Commencement Date.",
            ),
            (
                "lease-50-cheapside.pdf",
                12,
                "The Tenant shall keep the Premises in good and substantial "
                "repair and condition throughout the Term.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "summarise the key terms of this lease"
    )

    # FTS likely won't get >= 3 meaningful hits for this vague query.
    # Regardless of path, all chunks should be accessible to the LLM.
    assert len(results) == 4


# ---------------------------------------------------------------------------
# 9. Stemming — FTS should handle morphological variants
# ---------------------------------------------------------------------------


async def test_stemming_matches_plural_and_verb_forms(session: AsyncSession) -> None:
    """Searching 'assignments' should match 'assign' and 'assignment' via stemming."""
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                7,
                "The Tenant shall not assign, underlet, charge or part with "
                "possession of the whole or any part of the Premises without "
                "the prior written consent of the Landlord. Any assignment "
                "shall be subject to the Authorised Guarantee Agreement.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                8,
                "In the case of any permitted assignment, the outgoing Tenant "
                "shall enter into an Authorised Guarantee Agreement in the form "
                "set out in Schedule 5.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of One Hundred "
                "and Seventy-Five Thousand Pounds per annum exclusive of VAT.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "assignments", min_results=1
    )

    matched = _matched_keys(results)
    # PG English stemmer: 'assignments' -> 'assign', 'assign' -> 'assign',
    # 'assignment' -> 'assign'. All should match.
    assert ("lease-100-bishopsgate.pdf", 7) in matched
    assert ("lease-100-bishopsgate.pdf", 8) in matched
    assert _is_fts_path(results)
    # Assignment pages should rank in top 2 (precision)
    top2 = _top_n_keys(results, 2)
    assert ("lease-100-bishopsgate.pdf", 7) in top2
    assert ("lease-100-bishopsgate.pdf", 8) in top2
    # Rent clause should not match
    assert ("lease-100-bishopsgate.pdf", 3) not in matched


# ---------------------------------------------------------------------------
# 10. Red herring — similar vocabulary, different legal concept
# ---------------------------------------------------------------------------


async def test_rent_ranking_primary_vs_incidental(session: AsyncSession) -> None:
    """'Rent' query should rank the actual rent clause above insurance premium
    described as 'additional rent', though both technically mention 'rent'.

    This tests ranking quality: the primary rent clause (which mentions 'rent'
    multiple times) should rank higher than a clause where 'rent' appears
    only once as a payment mechanism label.
    """
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of One Hundred "
                "and Seventy-Five Thousand Pounds (£175,000) per annum "
                "exclusive of VAT, payable quarterly in advance on the usual "
                "quarter days. The rent shall be paid by standing order.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                15,
                "The Tenant shall pay to the Landlord a fair proportion of "
                "the insurance premium by way of additional rent. The Landlord "
                "shall insure the Building against the Insured Risks.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                10,
                "The Tenant shall not make any structural alterations to the "
                "Premises without the prior written consent of the Landlord.",
            ),
        ],
    )

    # Use just 'rent' — not 'annual rent' which would AND in 'annual' and miss
    # 'per annum' (different stems: 'annual' vs 'annum').
    results = await retrieve_chunks(
        session, conv_id, "rent", min_results=1
    )

    matched = _matched_keys(results)
    assert ("lease-100-bishopsgate.pdf", 3) in matched
    assert _is_fts_path(results)
    # Alterations clause doesn't mention rent
    assert ("lease-100-bishopsgate.pdf", 10) not in matched

    # Both page 3 and 15 mention 'rent', but page 3 should rank higher
    # because ts_rank rewards term frequency.
    rent_pages = [r for r in results if r.page_number == 3]
    insurance_pages = [r for r in results if r.page_number == 15]
    if rent_pages and insurance_pages:
        assert rent_pages[0].rank >= insurance_pages[0].rank


async def test_annual_vs_annum_stem_mismatch(session: AsyncSession) -> None:
    """Searching 'annual rent' fails FTS when document says 'per annum'.

    PostgreSQL English stemmer: 'annual' -> 'annual', 'annum' -> 'annum'.
    These are different stems despite being the same Latin root. Combined
    with websearch_to_tsquery's AND semantics, 'annual' & 'rent' won't match
    a chunk containing 'per annum' and 'rent' because 'annual' != 'annum'.
    This is a real gap that affects CRE documents where 'per annum' is the
    standard phrasing.
    """
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of One Hundred "
                "and Seventy-Five Thousand Pounds (£175,000) per annum "
                "exclusive of VAT, payable quarterly in advance on the usual "
                "quarter days.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "annual rent", min_results=1
    )

    # 'annual' stem doesn't match 'annum' stem -> FTS gets zero hits -> fallback
    assert not _is_fts_path(results)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# 11. Permitted use / planning — domain-specific compound term
# ---------------------------------------------------------------------------


async def test_permitted_use_search(session: AsyncSession) -> None:
    """Lawyer searches 'permitted use' — should match the use clause."""
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-50-cheapside.pdf",
                8,
                "The Tenant covenants to use the Premises solely for purposes "
                "falling within Class E of the Town and Country Planning (Use "
                "Classes) Order 1987 as amended, and for no other purpose "
                "whatsoever. The Tenant shall not use the Premises or permit "
                "them to be used for any illegal or immoral purpose.",
            ),
            (
                "lease-50-cheapside.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of Eighty "
                "Thousand Pounds (£80,000) per annum exclusive of VAT.",
            ),
            (
                "lease-50-cheapside.pdf",
                12,
                "The Tenant shall keep the Premises in good and substantial "
                "repair and condition throughout the Term.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "permitted use", min_results=1
    )

    matched = _matched_keys(results)
    # FTS: 'permitted' stems to 'permit', page 8 has 'permit' in text.
    # 'use' is in the page content too.
    assert ("lease-50-cheapside.pdf", 8) in matched
    assert _is_fts_path(results)


# ---------------------------------------------------------------------------
# 12. Title register cross-reference with lease
# ---------------------------------------------------------------------------


async def test_cross_reference_title_and_lease_by_address(session: AsyncSession) -> None:
    """Lawyer searches by address to find matching chunks across title register and lease.

    Using just 'Bishopsgate' avoids the AND-semantics problem: both the title
    register and lease mention 'Bishopsgate'. With a multi-term query like
    '100 Bishopsgate lease', the title register page 1 would be excluded
    because it doesn't contain the word 'lease'.
    """
    conv_id = await _seed_chunks(
        session,
        [
            (
                "title-register-NGL123456.pdf",
                1,
                "Title Number: NGL123456. The Freehold land shown edged with "
                "red on the plan of the above title filed at the Registry and "
                "being 100 Bishopsgate, London EC2M 1QS.",
            ),
            (
                "title-register-NGL123456.pdf",
                2,
                "CHARGES REGISTER. (1) A Lease dated 1 June 2018 for a term "
                "of 15 years from 1 June 2018 at a rent of £150,000 per annum "
                "granted to TechCo Services Limited. NOTE: The rent stated may "
                "have been varied by subsequent review.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                1,
                "THIS LEASE is made on the 1st day of June 2018 BETWEEN "
                "(1) Bishopsgate Property Holdings Limited (the 'Landlord') and "
                "(2) TechCo Services Limited (the 'Tenant') in respect of the "
                "Premises known as 100 Bishopsgate, London EC2M 1QS.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of One Hundred "
                "and Fifty Thousand Pounds (£150,000) per annum exclusive of "
                "VAT, payable quarterly in advance.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "Bishopsgate", min_results=1
    )

    doc_names = {r.document_filename for r in results}
    # Both documents reference 'Bishopsgate' — FTS should retrieve both
    assert "title-register-NGL123456.pdf" in doc_names
    assert "lease-100-bishopsgate.pdf" in doc_names
    assert _is_fts_path(results)


async def test_multi_term_address_query_fts_limitation(session: AsyncSession) -> None:
    """'100 Bishopsgate lease' with AND semantics excludes title register page 1.

    websearch_to_tsquery('english', '100 Bishopsgate lease') -> '100' & 'bishopsg' & 'leas'.
    Title register page 1 mentions '100 Bishopsgate' but not 'lease', so it
    fails the AND match. Only chunks containing ALL three terms qualify.
    This is a real limitation for cross-document queries where the user's
    query terms are split across documents.
    """
    conv_id = await _seed_chunks(
        session,
        [
            (
                "title-register-NGL123456.pdf",
                1,
                "Title Number: NGL123456. The Freehold land shown edged with "
                "red on the plan of the above title filed at the Registry and "
                "being 100 Bishopsgate, London EC2M 1QS.",
            ),
            (
                "title-register-NGL123456.pdf",
                2,
                "CHARGES REGISTER. (1) A Lease dated 1 June 2018 for a term "
                "of 15 years from 1 June 2018 at a rent of £150,000 per annum "
                "granted to TechCo Services Limited.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                1,
                "THIS LEASE is made on the 1st day of June 2018 BETWEEN "
                "(1) Bishopsgate Property Holdings Limited (the 'Landlord') and "
                "(2) TechCo Services Limited (the 'Tenant') in respect of the "
                "Premises known as 100 Bishopsgate, London EC2M 1QS.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "100 Bishopsgate lease", min_results=1
    )

    matched = _matched_keys(results)
    # Only lease page 1 has all three stems. Title register page 1 is excluded.
    assert ("lease-100-bishopsgate.pdf", 1) in matched
    assert _is_fts_path(results)
    # Title page 2 has 'lease' but not '100 Bishopsgate' directly — check
    # whether it matches (it has 'Lease' which stems to 'leas', but not '100')
    # Title page 1: has '100' and 'Bishopsgate' but not 'lease' -> excluded
    assert ("title-register-NGL123456.pdf", 1) not in matched


# ---------------------------------------------------------------------------
# 13. Service charge — multi-document with red herring
# ---------------------------------------------------------------------------


async def test_service_charge_with_red_herring(session: AsyncSession) -> None:
    """Lawyer searches 'service charge' — should match service charge clauses
    but not unrelated clauses mentioning 'service' in a different context.
    """
    conv_id = await _seed_chunks(
        session,
        [
            (
                "lease-100-bishopsgate.pdf",
                16,
                "The Tenant shall pay to the Landlord a service charge "
                "contribution calculated in accordance with Schedule 4 "
                "representing a fair proportion of the costs and expenses "
                "incurred by the Landlord in providing the services set out "
                "in Part 2 of Schedule 4.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                17,
                "Schedule 4 Part 2 — Landlord's Services. The Landlord shall "
                "provide the following services: (a) cleaning and maintenance "
                "of common parts; (b) operation of passenger lifts and "
                "escalators; (c) heating, ventilation and air conditioning of "
                "the common parts; (d) security of the Building.",
            ),
            (
                "licence-to-alter.pdf",
                1,
                "The Tenant shall serve notice on the Landlord not less than "
                "twenty working days prior to the commencement of any Works. "
                "Service of notices under this Licence shall be effected in "
                "accordance with section 196 of the Law of Property Act 1925.",
            ),
            (
                "lease-100-bishopsgate.pdf",
                3,
                "The Tenant shall pay to the Landlord a rent of One Hundred "
                "and Seventy-Five Thousand Pounds per annum exclusive of VAT.",
            ),
        ],
    )

    results = await retrieve_chunks(
        session, conv_id, "service charge", min_results=1
    )

    matched = _matched_keys(results)
    # The actual service charge clauses should match
    assert ("lease-100-bishopsgate.pdf", 16) in matched
    assert _is_fts_path(results)
    # Service charge page should rank first (precision)
    assert ("lease-100-bishopsgate.pdf", 16) in _top_n_keys(results, 1)

    # The licence notice clause mentions 'service' but in the context of
    # 'service of notices' — FTS will still match on the word 'service'.
    # This is a known FTS limitation: it cannot distinguish the legal context
    # of a word. The licence page MAY appear in results.
    # The important thing is the actual service charge page ranks higher.
    service_charge_results = [r for r in results if r.page_number == 16]
    notice_results = [
        r for r in results if r.document_filename == "licence-to-alter.pdf"
    ]
    if service_charge_results and notice_results:
        assert service_charge_results[0].rank >= notice_results[0].rank
