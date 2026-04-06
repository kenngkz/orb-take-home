# Coding Agent Guidelines

## External File Loading

When you encounter a file reference (e.g., @rules/backend.md), use your Read tool to load it on a need-to-know basis.

## Project Overview

Document Q&A tool for commercial real estate lawyers. Python backend + React frontend, orchestrated with Docker Compose.

- **Backend runtime:** Python 3.12
- **Frontend runtime:** Node.js 20
- **Backend package manager:** uv
- **Frontend package manager:** npm
- **Backend linter/formatter:** Ruff (100-char line length) + Pyright (strict)
- **Frontend linter/formatter:** Biome (tab indent, double quotes)
- **Task runner:** just (see `justfile` for all commands)
- **Database:** PostgreSQL 16 (via Docker Compose)
- **ORM:** SQLAlchemy 2.0+ (async)
- **Migrations:** Alembic (auto-run on startup)
- **LLM:** Pydantic-AI with Anthropic (Claude)

## Development

All services run in Docker. Use `just` commands:

- `just dev` — start full stack (Postgres, backend, frontend)
- `just check` — run all linters/typecheckers
- `just fmt` — format all code
- `just db-shell` — open psql shell
- `just db-migrate "message"` — create a new migration

## Rule Files

For backend patterns (FastAPI, SQLAlchemy, Pydantic): @rules/backend.md
For frontend patterns (React, TypeScript, Tailwind): @rules/frontend.md

## File Naming Conventions

- **Python:** `snake_case.py` (e.g., `conversation.py`, `llm.py`)
- **React components:** `PascalCase.tsx` (e.g., `ChatWindow.tsx`, `MessageBubble.tsx`)
- **Hooks:** `use-kebab-case.ts` (e.g., `use-conversations.ts`)
- **Other TS files:** `kebab-case.ts` (e.g., `api.ts`, `utils.ts`)

## Naming Conventions

- **Python:** `snake_case` for functions/variables, `PascalCase` for classes
- **TypeScript:** `camelCase` for functions/variables, `PascalCase` for types/interfaces/components
- **No `I` prefix** on interfaces — use plain `PascalCase`

## Imports

- **Backend:** Absolute from package root — `from takehome.services.llm import agent`
- **Frontend:** `@/*` alias maps to `./src/*` — `import { useConversations } from "@/hooks/use-conversations"`
- **Frontend type imports:** Use `import type { ... }` for type-only imports

## Testing

- **Backend:** pytest with pytest-asyncio (`asyncio_mode = "auto"`)
- **Run:** `docker compose exec backend uv run pytest`
- **Test directory:** `backend/tests/`
- **Frontend:** No test framework configured yet

## Code Style

- **Never use `as any`** in TypeScript — use proper types or type guards
- **Avoid unnecessary comments** — code should be self-documenting
- **Use sentence case** for UI text (e.g., "Upload document", not "Upload Document")
- **Python:** Use `from __future__ import annotations` at the top of every module
- **Python:** Use `structlog.get_logger()` for logging, not `print()` or stdlib `logging`

## Skills & Commands

Check available commands in `.claude/commands/` before starting tasks.
Use `/command-name` to invoke commands.
