# Citations

## Problem

Lawyers cannot act on AI-generated answers without verifiable sources. The baseline app produced free-text references like "page 3" with no link to the actual document -- useless for due diligence work where every claim must be traceable. We needed structured, clickable citations that navigate directly to the cited page in the PDF viewer.

## Prompt engineering

Getting Claude Haiku to cite reliably requires reinforcement at three layers:

1. **System prompt**: A `CITATION FORMAT -- MANDATORY` heading with an explicit few-shot example (`[title-report-lot-7.pdf, page 1]`) and a negative example (`WRONG: [Source: Official Title Report, Page 1]`). The instruction specifies that filenames must be copied verbatim from the `document` attribute of the `<chunk>` tag, not from the document's internal headings.

2. **User-prompt reminder**: Every turn prepends `IMPORTANT: Cite every fact using [filename.pdf, page N]` to the user's message, directly after the document context block. This per-turn nudge is critical -- system prompt alone is insufficient for smaller models, which drift from instructions over multi-turn conversations.

3. **Raw citations in conversation history**: Assistant messages are stored in the database with their original `[filename.pdf, page N]` text intact. When history is loaded for subsequent turns, the model sees its own prior citation pattern in-context, reinforcing the format through self-demonstration. Citation markers (`[1]`, `[2]`) are only substituted on output to the frontend.

All three layers are necessary. In testing, removing any single layer caused Haiku to intermittently drop citations or revert to free-text page references.

## Citation parser

`citations.py` extracts citations via regex: `\[([^,\]]+),\s*(?:page|p\.?)\s*(\d+)\]`. Each match is validated against the chunk set that was actually retrieved for the query -- any citation referencing a filename/page pair not present in the retrieved chunks is silently dropped. This prevents hallucinated citations from reaching the user. Matching is case-insensitive with canonical filename preservation. Duplicate (filename, page) pairs are deduplicated.

## Storage strategy

The raw LLM response (with `[filename.pdf, page N]` markers) is persisted to the `messages` table alongside a parsed `citations` JSON column. On read, `replace_citations_with_markers()` substitutes raw citations with numbered markers (`[1]`, `[2]`) keyed to the citations array. Invalid citations not in the parsed list are stripped entirely. This dual representation serves both history reinforcement (raw in DB) and clean display (numbered on output).

## Frontend rendering

Streamdown (the markdown renderer) sanitizes HTML, so we cannot inject `<button>` elements pre-render. Instead, `MessageBubble` runs a DOM `TreeWalker` post-render (`useEffect` on `message.citations`) that finds text nodes matching `/\[(\d+)\]/g` and replaces them with styled `<button>` elements carrying `data-cite` attributes. Click handling uses event delegation: a single `onClick` on the prose container reads `e.target.dataset.cite` to resolve the citation index.

Below the message body, a citation footer renders pill-shaped buttons for each source, showing the filename and page number.

## Click navigation

Citation click (inline or footer pill) calls `onCitationClick(documentId, pageNumber)` which propagates up to `App.tsx`. There, `handleCitationClick` calls `selectDocument(docId)` to switch the active document tab, then sets `targetPage` via a `queueMicrotask` pattern (reset to `null` then set) to ensure the `useEffect` in `PdfContent` fires even when navigating to the same page twice. `PdfContent` watches `targetPage` and calls `setCurrentPage(targetPage)` to scroll the PDF viewer.

## Known limitations

- **Regex parsing is brittle.** Citations with unexpected formatting (extra commas, nested brackets) will be missed. Structured output via tool use would be more robust, but adds latency to every streamed response.
- **Haiku still occasionally skips citations** despite all three reinforcement layers, particularly in summary-style answers where it generalises across multiple pages.
- **No sub-page anchoring.** Navigation is page-level only -- the viewer scrolls to the page but not to the specific paragraph.
