---
description: Access the dev Postgres database via Docker Compose
---

## What I do

- Inspect and debug data in the dev Postgres database
- Run read queries (SELECT, \d, \dt, etc.)
- Run write queries **only after explicit user approval**

## Running Commands

Use Docker Compose to access the Postgres container:

```bash
docker compose exec db psql -U orbital orbital_takehome -c "<sql>"
```

Or use the justfile shortcut for an interactive shell:

```bash
just db-shell
```

### Examples

List tables:

```bash
docker compose exec db psql -U orbital orbital_takehome -c "\dt"
```

Describe a table:

```bash
docker compose exec db psql -U orbital orbital_takehome -c "\d conversations"
```

Run a SELECT query:

```bash
docker compose exec db psql -U orbital orbital_takehome -c "SELECT id, title FROM conversations LIMIT 10;"
```

## Read vs Write Safety

**Reads are safe** — run freely without confirmation:
`SELECT`, `\d`, `\dt`, `\di`, `\dn`, `\df`, `\du`, `EXPLAIN`, `SHOW`, and any other query that does not modify data.

**Writes MUST be confirmed by the user before execution.** Always:

1. Show the exact SQL you intend to run
2. Explain what it will do
3. Wait for explicit user approval before running

Write operations include:
`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `CREATE`, and any other statement that modifies schema or data.

**IMPORTANT:** `DROP`, `TRUNCATE`, and `DELETE` without a `WHERE` clause are destructive. Treat them with extreme caution — double-confirm with the user.

## Troubleshooting

### Container not running

```bash
just dev-detach
```

Then retry the query.

## When to use me

Use this skill when:

- Inspecting or debugging database tables and rows
- Checking schema structure (columns, indexes, constraints)
- Running ad-hoc SELECT queries against the dev database
- Diagnosing data issues
- Any direct psql interaction against the dev instance
