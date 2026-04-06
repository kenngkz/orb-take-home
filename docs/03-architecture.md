# Architecture

## System overview

Three-panel app: sidebar (conversations) | chat (Q&A) | document viewer (PDF).

```
User query
    |
    v
[Query generation] -- rewrites follow-ups into standalone retrieval queries
    |
    v
[PostgreSQL FTS] ----+
                     |--> RRF merge --> token budget --> LLM (Haiku) --> SSE stream
[pgvector cosine] ---+
```

All services run in Docker Compose: PostgreSQL 16 (pgvector), Python/FastAPI backend, React/Vite frontend.

## Retrieval pipeline

See [docs/04-retrieval.md](04-retrieval.md) for the full deep-dive.

### Chunking

Page-level chunks. Each PDF page becomes a `DocumentChunk` row with `document_id`, `page_number`, `content`, and `embedding` (vector(384)). Pages with no extractable text are skipped.

**Why page-level:** Lawyers think in pages. Citations need page references that map directly to the PDF viewer. Each chunk includes trailing context from the previous page (3 sentences) to capture clauses that span page boundaries without breaking the page-to-citation mapping.

### Hybrid search

Two parallel retrieval paths merged with Reciprocal Rank Fusion (RRF):

1. **PostgreSQL FTS** (`websearch_to_tsquery` + GIN index) — keyword matching. Handles exact legal terms well ("break clause", "rent review"). Uses `websearch_to_tsquery` over `plainto_tsquery` because it supports OR semantics and quoted phrases, which matters for multi-word legal queries.

2. **pgvector cosine similarity** (HNSW index) — semantic matching via `BAAI/bge-small-en-v1.5` embeddings (384-dim, local ONNX via fastembed). Catches synonym gaps FTS misses: "termination" finds "break clause", "dilapidations" finds "repair obligations".

3. **RRF merge** — `score = sum(1/(60 + rank))` across both lists. Standard approach that avoids score normalization issues between FTS `ts_rank` and cosine distance.

### Fallback strategy

If hybrid search returns fewer than 3 results (broad queries like "summarise the key terms"), falls back to all chunks in reading order. Both paths enforce a token budget (80k tokens) to avoid blowing the context window.

### Graceful degradation

- Embedding fails at upload → chunks stored without vectors, FTS-only retrieval
- Embedding fails at query time → FTS-only retrieval
- FTS fails → vector-only retrieval
- Both fail → full context fallback

## LLM integration

- **Model:** Claude Haiku 4.5 via Pydantic-AI (separate lightweight agents for title generation and query generation)
- **Query generation:** Follow-up messages are rewritten into standalone retrieval queries using a lightweight LLM call before search. Resolves pronouns and implicit references ("what about the break clause?" → "break clause provisions in the lease agreement"). First messages skip this step.
- **Conversation history:** Pydantic-AI `message_history` with proper role-tagged turns and a 20-turn sliding window
- **Document context:** Chunks formatted as `<chunk document="filename" page="N">` XML tags. System prompt instructs the model to cite using these attributes.
- **Streaming:** SSE with `content` → `message` → `done` events. Title generation runs after `done` event to avoid blocking the client.
- **Security:** HTML escaping on chunk content and filenames before prompt injection. UUID-only filenames on disk (user-facing names in DB only).

## Citation pipeline

See [docs/05-citations.md](05-citations.md) for the full deep-dive.

1. **Prompt engineering** — three reinforcement layers: system prompt (few-shot + negative example), per-turn user-prompt reminder, raw citations preserved in conversation history for model self-demonstration.
2. **Parser** — regex extracts `[filename.pdf, page N]` from LLM output, validates against retrieved chunks (rejects hallucinated citations), deduplicates.
3. **Storage** — raw response stored in DB (history reinforcement), numbered markers `[1]`, `[2]` substituted only on output to frontend.
4. **Frontend** — DOM post-processing injects clickable button elements into Streamdown's rendered output. Citation pills below each message. Click navigates the PDF viewer to the cited document + page.

## Data model

```
Conversation 1---* Message
Conversation 1---* Document
Document     1---* DocumentChunk (page_number, content, embedding)
```

All IDs are 16-char hex (truncated UUID4). Foreign keys cascade on delete. Documents clean up disk files on deletion.

## Testing

See [docs/06-testing.md](06-testing.md) for the full strategy.

65 tests across 6 files:
- **Conversation CRUD** (5 tests)
- **Document upload + chunking** (10 tests)
- **FTS retrieval unit** (8 tests) — matching, exclusion, fallback, token budget
- **FTS retrieval integration** (18 tests) — realistic CRE legal queries, documents FTS limitations (synonym gaps, AND semantics)
- **Hybrid search** (11 tests) — RRF merge, embedding pipeline, vector search proves semantic matching works where FTS fails
- **Citation parser** (13 tests) — extraction, validation, deduplication, marker replacement

## Known limitations

- **Page-level chunking** — cross-page clauses are split. No overlap between chunks.
- **No reranking** — RRF merge is the only quality gate between retrieval and generation.
- **Regex citation parsing** — brittle compared to structured LLM output via tool use.
- **Haiku citation reliability** — still occasionally skips citations despite three reinforcement layers.
- **No conversation history summarization** — sliding window truncates, doesn't summarize.
