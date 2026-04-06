# Codebase Exploration

## Architecture Overview

Barebones document Q&A app: React frontend + FastAPI backend + PostgreSQL, orchestrated with Docker Compose.

## Backend (Python 3.12, FastAPI)

### Structure
```
backend/src/takehome/
├── config.py              # Pydantic settings (DB URL, API key, upload dir)
├── db/
│   ├── models.py          # 3 tables: Conversation, Message, Document
│   └── session.py         # Async session factory (asyncpg)
├── services/
│   ├── conversation.py    # CRUD for conversations
│   ├── document.py        # PDF upload + PyMuPDF text extraction
│   └── llm.py             # Pydantic-AI agent with Claude Haiku 4.5
└── web/
    ├── app.py             # FastAPI app, CORS, lifespan (auto-migrate)
    └── routers/
        ├── conversations.py  # GET/POST/PATCH/DELETE /api/conversations
        ├── documents.py      # POST upload, GET serve PDF
        └── messages.py       # GET messages, POST message (SSE streaming)
```

### Database Schema (1 migration: 001_initial_schema)
- **conversations**: id, title, created_at, updated_at
- **messages**: id, conversation_id (FK), role, content, sources_cited, created_at
- **documents**: id, conversation_id (FK), filename, file_path, extracted_text, page_count, uploaded_at

### LLM Integration (llm.py) — The Naive Part
- Single Pydantic-AI agent using `claude-haiku-4-5-20251001`
- System prompt: "legal document assistant, cite sources, no fabrication"
- **No RAG**: full document text dumped into `<document>` tags as context
- **No chunking**: entire extracted text stored in one DB field
- **No embeddings**: no semantic search at all
- Conversation history sent as plaintext "User: ... / Assistant: ..."
- Source counting via regex (matches "section \d+", "clause \d+", etc.)
- Title generation via separate LLM call

### Document Processing (document.py)
- Max 25MB PDF upload
- PyMuPDF extracts text page-by-page with `--- Page N ---` markers
- **One document per conversation** (enforced in service layer)
- No OCR capability for scanned documents

### Streaming
- Backend: `agent.run_stream()` → yields text deltas
- SSE events: `{"type": "content", "content": "..."}` → `{"type": "message", ...}` → `{"type": "done", ...}`

## Frontend (React 18, TypeScript, Vite, Tailwind)

### Structure
```
frontend/src/
├── App.tsx           # Root: composes 3 hooks, passes props down
├── types.ts          # Conversation, Message, Document interfaces
├── components/
│   ├── ui/           # shadcn/ui (button, card, dialog, scroll-area, tooltip)
│   ├── ChatSidebar   # Conversation list, create/delete
│   ├── ChatWindow    # Message display, auto-scroll
│   ├── MessageBubble # User/assistant/system message rendering (Streamdown)
│   ├── ChatInput     # Textarea + file upload button
│   ├── DocumentViewer # react-pdf viewer, resizable panel, page navigation
│   ├── DocumentUpload # Drag-drop zone
│   └── EmptyState    # Onboarding UI
├── hooks/
│   ├── use-conversations.ts  # CRUD + list state
│   ├── use-messages.ts       # Messages + SSE streaming
│   └── use-document.ts       # Document upload + state
└── lib/
    ├── api.ts        # Fetch-based API client, SSE parser
    └── utils.ts      # cn(), relativeTime()
```

### Key Patterns
- No external state library — hooks + lifted state in App.tsx
- Streaming via fetch ReadableStream + manual SSE parsing
- Markdown via Streamdown library (streaming mode)
- Animations via Framer Motion
- PDF viewer via react-pdf + pdfjs-dist
- Resizable document panel (280-700px)

## Infrastructure

### Docker Compose
- **db**: PostgreSQL 16 Alpine (healthcheck, persistent volume)
- **backend**: Python 3.12, uvicorn with --reload, source mounted
- **frontend**: Node 20, Vite dev server, source mounted

### Just Commands
- `just dev` / `just stop` / `just reset`
- `just check` / `just fmt` (backend + frontend linting)
- `just db-shell` / `just db-migrate` / `just db-upgrade`
- `just shell-backend` / `just shell-frontend`

### Test Documents
**synthetic-docs/** (clean, machine-generated):
- `commercial-lease-100-bishopsgate.pdf` (24KB)
- `title-report-lot-7.pdf` (8KB)
- `environmental-assessment-manchester.pdf` (20KB)

**real-docs/** (scanned, visual):
- `Lease (06-06-2008).pdf` (13MB — large scanned lease)
- `Official Copy (NGL885533 - Deed - 31-03-2016).pdf` (612KB)
- `Rent review memorandum - 8th Fl, Building 5, New Street Sq.pdf` (12KB)

### Tests
- Empty `backend/tests/` directory — no tests written yet.

## What's Naive / Needs Work

1. **No multi-document support** — one doc per conversation, hardcoded
2. **No retrieval** — entire doc text sent as context (won't scale past ~50 pages)
3. **No chunking or embeddings** — no semantic search
4. **No real citations** — regex counts mentions, no links to source locations
5. **No document hierarchy awareness** — can't reason about which doc supersedes another
6. **Regex source counting** — brittle, misses many citation patterns
7. **No tests** — empty test directory
8. **Synchronous file I/O in async context** — blocks event loop
