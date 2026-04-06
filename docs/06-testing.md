# Testing

## Overview

65 tests across 6 files, all running against a real PostgreSQL database with the pgvector extension. No mocks for database operations. This is deliberate: retrieval correctness depends on actual PostgreSQL full-text search (FTS) ranking, tsvector/tsquery parsing, English stemmer behavior, and pgvector cosine distance. Mocking any of these would make the tests meaningless.

## Test categories

| File | Tests | Scope |
|---|---|---|
| `test_conversations.py` | 5 | Conversation CRUD via HTTP (create, list, get, delete, fixture validation) |
| `test_documents.py` | 10 | Document upload, multi-upload, listing, deletion, cascade, chunking, empty-page handling, conversation-document relationship |
| `test_retrieval.py` | 8 | FTS unit tests: keyword matching, irrelevant-chunk exclusion, fallback on zero/few matches, cross-document retrieval, token budget capping, metadata propagation |
| `test_retrieval_integration.py` | 18 | Realistic CRE legal queries against FTS (detailed below) |
| `test_hybrid_search.py` | 11 | RRF merge (5 pure-function tests), embedding pipeline (3 tests), vector search (2 DB tests), hybrid retrieval integration (1 test) |
| `test_citations.py` | 13 | Citation extraction, validation against chunk list, deduplication, case-insensitive matching, page-number variants (`page`, `p.`, `p`), marker replacement (`[1]`, `[2]`), invalid/missing citation handling |

## Integration tests as documentation

The 18 FTS integration tests in `test_retrieval_integration.py` serve double duty. They verify retrieval quality AND document known limitations of PostgreSQL FTS for CRE legal text.

**10 tests show successful retrieval:** simple rent lookup, cross-document rent comparison, break clause exact match, multi-term "rent review" query, insurance across documents, stemming (assignments/assign/assignment), permitted use, address-based cross-reference, rent ranking by term frequency, service charge with red herring.

**5 tests document where FTS fails:**
- "termination rights" vs "break clause" -- synonym gap, different stems (`termin` vs `determin`)
- "dilapidations liability" vs "repair obligations" -- domain jargon not linked by stemmer
- "rent review mechanism" -- AND semantics require every term present; no chunk contains "mechanism"
- "insurance obligations" -- documents say "shall insure" but never "obligation"
- "annual rent" vs "per annum" -- Latin/English stem mismatch (`annual` != `annum`)

These 5 failures are the evidence that motivated adding vector search.

## Hybrid search tests

The 11 tests in `test_hybrid_search.py` prove vector search fills the gaps FTS misses. The key test: querying "termination" retrieves "break clause" content via embeddings where FTS returns nothing -- the same query that fails in the FTS integration tests. Additional tests verify RRF merge scoring (shared items rank higher than single-list items, disjoint lists preserve all items, correct score calculation), embedding pipeline output (384-dimensional vectors from the local sentence-transformers model), and hybrid merge of FTS + vector results for queries like "rent" where both keyword and semantic matches contribute.

## What's not tested

- **LLM output quality**: non-deterministic; testing prompt+retrieval is more valuable at this scope
- **Frontend components**: no test framework configured (acceptable for take-home)
- **SSE streaming endpoint**: would require end-to-end async stream consumption; retrieval and citation logic are tested independently

## Test infrastructure

`conftest.py` sets up the test database using the same connection URL as the app (Docker Compose provides isolation). On each test: creates the pgvector extension and all tables via SQLAlchemy metadata, yields control to the test, then truncates every table with `CASCADE`. Uses `NullPool` to avoid connection pool conflicts between fixture setup and app handlers. Provides three fixtures: raw `AsyncSession` for direct DB operations, `AsyncClient` (httpx over ASGI transport) for HTTP tests, and factory fixtures for pre-built `Conversation` and `Document` objects.
