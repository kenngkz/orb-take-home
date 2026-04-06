# Implementation Plan

## Architecture Decisions

### Retrieval Strategy
**Chunk + embed + vector search (pgvector)**. Legal docs are keyword-heavy, but semantic search catches paraphrasing. pgvector adds minimal infra (just a PG extension) and is the right architectural primitive. Embedding via a local model (e.g. fastembed) — no extra API keys needed.

### Chunking Strategy
**Page-level chunks** — the natural unit for legal docs. Lawyers think in pages and page references. Stored with metadata: document_id, page_number, section headings if detectable. Directly supports citations.

### Citation Format
**Hybrid streaming**: stream answer text with `[1]`, `[2]` inline markers, then send a final SSE event with structured citation data mapping each marker to document/page/quote. Frontend renders markers as clickable links.

### Context Building
Retrieved top-k chunks grouped by document, presented to the LLM with numbered labels:
```
[1] Document: "Lease (2008)", Page 12, Section 4.2
{chunk text}

[2] Document: "Deed of Variation", Page 3, Section 2.1
{chunk text}
```

---

## Implementation Steps

### Step 0: Testing Foundation
- conftest.py with async test DB, session fixtures, test client
- Factory helpers for creating test conversations/documents
- Unblocks testing at every subsequent step

### Step 1: Multi-Document Support
- Update DB schema: remove 1-doc-per-conversation constraint
- Update API: multi-doc upload, list documents per conversation
- Update frontend: multi-doc upload UI, document list/selector
- **Tests**: multi-doc upload/list endpoints

### Step 2: Chunking Pipeline
- On upload: split document text by page
- Store chunks in new `document_chunks` table with metadata (doc_id, page_number, section, text)
- **Tests**: chunking logic produces correct chunks with metadata

### Step 3: Retrieval + Cross-Doc Prompting → Feature 1 Complete
- Add pgvector extension to PostgreSQL
- Generate embeddings for chunks on upload (local model, no API key)
- On query: embed query, retrieve top-k relevant chunks across all documents
- Updated system prompt that reasons across documents and synthesizes
- **Tests**: retrieval returns relevant chunks for known queries

### Step 4: Structured Citations from LLM → Feature 2 Backend
- Update LLM prompt to return citation markers `[1]`, `[2]` with structured metadata
- Update SSE protocol: new event type for citation data
- Parse and validate citation output
- **Tests**: citation parsing, SSE event format

### Step 5: Citation UX → Feature 2 Complete
- Frontend renders inline `[1]` markers as clickable links
- Clicking a citation navigates document viewer to correct document + page
- Citation tooltip/popover showing quote preview

### Step 6: Final
- APPROACH.md (~1 page): architecture decisions, priorities, tradeoffs
- End-to-end test with full synthetic document bundle
- Final review and cleanup
