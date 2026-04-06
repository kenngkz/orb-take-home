# Retrieval pipeline

## Why hybrid search

CRE lawyers ask questions that break any single retrieval method. Full-text search handles exact legal terminology well ("break clause", "service charge") but fails on synonym gaps: a lawyer searching "termination rights" won't find a clause titled "break clause" because PostgreSQL's English stemmer treats "termin" and "break" as unrelated stems. Conversely, pure vector search handles semantic similarity but is worse at exact multi-word legal terms and quoted phrases where keyword precision matters.

Hybrid search (FTS + vector, merged with RRF) covers both cases without requiring either method to be perfect.

## PostgreSQL full-text search

Uses `websearch_to_tsquery` with the English stemming config, backed by a GIN index on `to_tsvector('english', content)`. Chosen over `plainto_tsquery` because it supports quoted phrases (`"break clause"`) and OR operators, both useful for legal queries.

Strengths:
- **Exact legal terms** -- "break clause", "rent review", "service charge" all match directly via stems.
- **Stemming** -- searching "assignments" matches chunks containing "assign" and "assignment" (all stem to `assign`).
- **Cross-document keyword hits** -- "insurance" retrieves matching clauses from both a lease and a licence to alter.
- **Ranking by term frequency** -- `ts_rank` scores a dedicated rent clause (mentions "rent" 3x) higher than an insurance clause that incidentally says "additional rent" once.

Limitations:
- **AND semantics** -- `websearch_to_tsquery('rent review mechanism')` requires all three stems present. If no chunk contains "mechanism", zero results. Same problem with "insurance obligations" where legal drafters write "the Tenant shall insure" without the word "obligation".
- **Stem mismatches** -- "annual" and "annum" have different stems despite the same Latin root. "annual rent" fails to match "per annum".
- **No synonym awareness** -- "termination" does not match "break clause". "Dilapidations" does not match "repair obligations".

## Vector search

Embeddings via `BAAI/bge-small-en-v1.5` -- a 384-dimensional model run locally through fastembed (ONNX runtime). Stored in pgvector with an HNSW index, queried by cosine distance.

**Why local over API:** No data leaves the server. CRE lease documents are confidential. Local inference also eliminates per-query API costs and latency, and removes an external dependency that could fail. The model is small enough (33M params) to load in the backend container at startup.

**What it catches that FTS misses:**
- "termination" finds the break clause chunk (semantic similarity to "end the lease", "determine this Lease") even though the word "termination" never appears.
- "dilapidations" finds repair obligation clauses via conceptual proximity.
- "rent review mechanism" retrieves rent review clauses despite the missing keyword "mechanism".

The embedding service uses `embed_query()` (with query-specific prefix) for search and `embed_texts()` for batch indexing at upload time.

## RRF merge

Reciprocal Rank Fusion merges the two ranked lists:

```
score(chunk) = sum(1 / (k + rank_position)) across all lists where chunk appears
```

With `k = 60` (standard default). A chunk appearing at position 0 in both lists scores `1/61 + 1/61 = 0.0328`. A chunk at position 0 in one list only scores `1/61 = 0.0164`.

RRF uses rank positions, not raw scores. This is the key property: `ts_rank` values (small floats like 0.06) and cosine distances (0.0-2.0) live on completely different scales. Any weighted-sum approach would require score normalization, which is fragile and dataset-dependent. RRF sidesteps the problem entirely.

## Fallback strategy

Graceful degradation at every level:

1. **Embedding failure** (model not loaded, OOM) -- logs warning, continues with FTS results only.
2. **FTS failure** (malformed query) -- logs warning, continues with vector results only.
3. **Both return < `min_results` (default 3)** -- falls back to all chunks in reading order. This handles vague queries ("summarise the key terms") where neither method produces enough hits.
4. **Both fail** -- same full-context fallback.

All paths enforce a **token budget of 80k tokens** (estimated at ~4 chars/token). Chunks are included in rank order until the budget is exhausted, so the most relevant content always fits even with large document sets.

## Example query behavior

| Query | FTS | Vector | Notes |
|---|---|---|---|
| "break clause" | Hits | Hits | Exact legal term, both methods work |
| "termination rights" | Misses | Hits | Synonym gap -- FTS can't link "termination" to "break clause" |
| "dilapidations liability" | Misses | Hits | UK CRE jargon for breach of repair covenants |
| "rent review" | Hits | Hits | Both terms present in review clauses |
| "rent review mechanism" | Misses | Hits | AND semantics -- "mechanism" absent from all chunks |
| "annual rent" | Misses | Hits | Stem mismatch -- "annual" vs "annum" |
| "insurance" | Hits | Hits | Single keyword, cross-document retrieval |
| "summarise the key terms" | Misses | Misses | Too vague for either method -- full-context fallback |
