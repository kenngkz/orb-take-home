# Approach

## What I built

A hybrid retrieval pipeline (PostgreSQL FTS + pgvector embeddings + Reciprocal Rank Fusion) with structured, clickable citations for a multi-document CRE Q&A tool. Both features focus on the core problem: lawyers need accurate, verifiable answers across document bundles.

## Architecture decisions

**Hybrid search.** CRE legal queries break any single retrieval method. FTS handles exact terms well ("break clause", "rent review") but fails on synonym gaps — a lawyer searching "termination rights" won't find a clause titled "break clause". Embeddings (BAAI/bge-small-en-v1.5 via fastembed, local ONNX inference) catch these semantic gaps. RRF merges the two ranked lists using rank positions rather than raw scores, sidestepping the incompatible score spaces problem between `ts_rank` floats and cosine distances. The system degrades gracefully at every layer: embedding failure falls back to FTS-only, FTS failure falls back to vector-only, both failing returns all chunks in reading order. See [docs/retrieval.md](docs/retrieval.md).

**Page-level chunking with overlap.** Each PDF page becomes one chunk, giving a clean 1:1 mapping between citations and the PDF viewer. Cross-page clauses get split — mitigated by prepending trailing context from the previous page to each chunk. This captures clause continuations (e.g., a rent review schedule spanning pages 14-16) while preserving the page-to-citation mapping.

**Local embeddings.** fastembed runs a 33M-parameter model locally via ONNX. No document data leaves the server (CRE leases are confidential), no per-query API costs, no external dependency that could fail. Quality is sufficient for the synonym gap problem that motivated adding embeddings. In production I'd use a more powerful embedding model and a more capable generation model (Sonnet/Opus).

**Query generation.** Follow-up messages like "what about the break clause?" lack context without the conversation history. A lightweight LLM call rewrites the user's message into a standalone retrieval query before search, resolving pronouns and implicit references. First messages skip this step (no history = no rewriting needed).

## Citations — the hard problem

Getting Haiku to cite reliably required three reinforcement layers: a system prompt with few-shot and negative examples, a per-turn reminder in the user message, and raw `[filename.pdf, page N]` citations preserved in conversation history so the model sees its own citation pattern. Removing any single layer caused Haiku to intermittently drop citations. The parser validates every citation against the retrieved chunk set — hallucinated references are filtered out. On the frontend, citations render as inline numbered markers and clickable pills that navigate the PDF viewer to the exact page. See [docs/citations.md](docs/citations.md).

## Priorities

Depth on retrieval and citations over feature breadth, with an emphasis on making continuous development easy. 65 tests — including 18 integration tests with realistic CRE queries that document exactly where FTS fails and embeddings fill the gap. An extensible E2E evaluator (parallel Playwright agents, scenario-driven) that can be re-run as features are added. Detailed architecture and design docs that serve as onboarding material. The goal was a codebase that's ready for the next engineer to pick up and extend, not just a demo that works today. See [docs/testing.md](docs/testing.md).

## Interesting problems

- **Haiku citation reliability** — system prompt alone was insufficient. Conversation history was actively undermining it: stripped citations taught the model not to cite on follow-ups. Storing raw citations in the DB for history reinforcement was the key insight. A more powerful model would likely need fewer workarounds, but this was a useful exercise in what to do when prompting alone isn't enough.
- **RRF for incompatible score spaces** — `ts_rank` and cosine distance live on completely different scales. RRF elegantly sidesteps this by using rank positions instead of scores, requiring no normalization.
- **Interactive elements inside a sanitizing renderer** — Streamdown strips HTML, so citation buttons can't be injected pre-render. DOM TreeWalker post-processing replaces `[N]` text nodes with clickable button elements — a pragmatic escape hatch when a library doesn't expose the hooks you need.
- **Harness-style AI development** — inspired by Anthropic's [long-running app design patterns](https://www.anthropic.com/engineering/harness-design-long-running-apps). Used sub-agents extensively: parallel adversarial code reviewers (4 agents reviewing independently without knowing the implementation), parallel E2E evaluators (4 browser agents testing simultaneously via Playwright), and parallel implementation agents for backend/frontend work. First time implementing this pattern — the adversarial reviews caught issues (silent debug-level logging, invalid nested DOM elements, stale React closures) that manual review would have missed.

## Scalability

The hybrid search (GIN index + HNSW index) scales well to 12-50 documents — both indexes query in O(log n) regardless of document count. The weak point is the fallback path: vague queries that trigger "all chunks in reading order" get token-budget-capped in upload order, biasing toward earlier documents. At 50 documents this needs document-level routing — an LLM step that identifies which documents are relevant before chunk retrieval — and query decomposition for multi-part questions like "compare the rent review provisions across all leases."

## What I'd do next

- **Agentic retrieval loop** — replace the single retrieve-then-generate pass with a tool-using agent that can issue multiple retrieval calls. "Compare the rent review provisions across all leases" becomes a loop: the agent searches each lease individually, accumulates findings, then synthesises. This is the single biggest capability unlock — it turns the system from a one-shot RAG into a genuine research agent
- **Structured citations via tool use** — define a `cite(filename, page)` tool in the Anthropic API so citations arrive as structured JSON alongside generated text, eliminating regex parsing entirely
- **Cross-encoder reranking** — add a reranking step (e.g., `ms-marco-MiniLM-L-6-v2`) between retrieval and generation. RRF merges by rank position but doesn't score query-document relevance directly
- **Domain knowledge** — the most impactful extension. Pre-embed a CRE legal ontology mapping domain concepts ("dilapidations" → "breach of repair covenants"), or add a CRE-specific thesaurus to PostgreSQL's FTS configuration
- **Web search tool** — trivial to add with the existing architecture; useful for planning context, market comparables, and regulatory lookups

## Tools

Built with Claude Code throughout — architecture planning, implementation, code review, and testing. Claude Haiku 4.5 for generation, fastembed (BAAI/bge-small-en-v1.5) for local embeddings.
