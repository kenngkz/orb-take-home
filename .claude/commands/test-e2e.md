---
description: Run E2E evaluation via Playwright MCP (parallel sub-agents)
---

You are the **E2E test coordinator**. You orchestrate parallel sub-agents to evaluate the app quickly.

## Setup

1. Read `e2e/scenarios.md` to load all test scenarios.
2. Check that test PDFs exist in `e2e/fixtures/`.
3. Ensure `e2e-screenshots/` directory exists (create if needed). **All screenshots MUST be saved there** — never save PNGs to the project root.

## Execution strategy

Split the scenarios into **independent groups** that can run in parallel as sub-agents. Each sub-agent gets its own browser session.

Launch these sub-agents **simultaneously** using the Agent tool:

### Agent 1: "Core navigation"
Scenarios: App loads, Create and delete conversation, Page navigation.
Instructions: Navigate to http://localhost:5173. Test app loading, conversation CRUD, and PDF page navigation. For page nav, create a conversation and upload `e2e/fixtures/lease-agreement.pdf` first. Take screenshots after each step — **save all screenshots to `e2e-screenshots/` with descriptive names** (e.g., `e2e-screenshots/nav-01-app-loads.png`). Use `mcp__playwright__browser_snapshot` to verify DOM state. Check console errors with `mcp__playwright__browser_console_messages`. Report verdict (PASS/FAIL) and notes for each scenario.

### Agent 2: "Document management"
Scenarios: Upload single document, Upload multiple documents, Switch between documents, Delete a document.
Instructions: Navigate to http://localhost:5173. Create a fresh conversation. Upload `e2e/fixtures/lease-agreement.pdf`, verify it renders. Then upload `e2e/fixtures/rent-review.pdf`, verify tabs appear. Switch between docs, verify PDF updates and page resets. Delete one doc, verify tab bar updates. Take screenshots after each step — **save all screenshots to `e2e-screenshots/` with descriptive names** (e.g., `e2e-screenshots/docs-01-upload-single.png`). Use `mcp__playwright__browser_snapshot` to verify DOM state. Check console errors. Report verdict and notes for each scenario.

### Agent 3: "Chat and Q&A"
Scenarios: Send message and receive response, Multi-document question.
Instructions: Navigate to http://localhost:5173. Create a conversation, upload both PDFs from `e2e/fixtures/`. Send "What is the annual rent in the lease agreement?" and wait up to 30s for streaming response. Take screenshot — **save all screenshots to `e2e-screenshots/` with descriptive names** (e.g., `e2e-screenshots/chat-01-single-doc-response.png`). Then send "Compare the proposed rent in the rent review with the current rent in the lease" and wait for response. Take screenshot. Verify responses reference correct documents by name. Report verdict and notes.

### Agent 4: "Robustness and quality"
This agent does the holistic evaluation. **Save all screenshots to `e2e-screenshots/` with descriptive names** (e.g., `e2e-screenshots/robust-01-no-doc-message.png`). Instructions: Navigate to http://localhost:5173. Test edge cases:
- Send a message with no document uploaded — does the app handle it gracefully?
- Try to send an empty message — is the send button disabled or does it error?
- Double-click "New chat" rapidly — are duplicate conversations created?
- Reload the page — does the selected conversation persist?
- Check all console errors/warnings.
Then assess quality:
- **Design**: Coherent visual language? Professional or scaffolding? Readable typography?
- **UX**: Loading states? Error states? Empty states helpful? Responsive?
- **Functional**: Console errors? All clickable elements work? State persistence?
- **Robustness**: Edge cases handled?
Rate each 1-5 and list all issues found with severity (CRITICAL/MAJOR/MINOR/COSMETIC).

## After all agents complete

Compile the results into a single report:

### Scenario results table
```
Scenario                        | Verdict | Notes
--------------------------------|---------|------
...
```

### Quality grades (from Agent 4)
- **Design quality**: X/5
- **UX quality**: X/5
- **Functional quality**: X/5
- **Robustness**: X/5

### Issues found (merged from all agents, deduplicated, ordered by severity)

### What works well (2-3 genuine positives)
