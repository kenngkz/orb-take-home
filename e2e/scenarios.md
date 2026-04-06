# E2E Test Scenarios

User flows verified by the `/test-e2e` evaluator via Playwright MCP.

## How to add scenarios

Add a new `## Scenario:` section with:
- **Preconditions**: state required before the scenario starts
- **Steps**: numbered actions to perform
- **Expected**: what to verify (visual + functional)

## Quality criteria (used in holistic evaluation)

- **Design**: Coherent visual language, professional feel, readable typography
- **UX**: Loading states, error handling, empty states, responsiveness
- **Functional**: No console errors, state persistence, all interactions work
- **Robustness**: Edge cases (empty input, rapid clicks, no docs, page reload)

---

## Scenario: App loads

**Preconditions**: App running at http://localhost:5173

**Steps**:
1. Navigate to http://localhost:5173
2. Take a screenshot

**Expected**:
- Sidebar visible on the left with "New conversation" button
- Main area shows empty state or welcome message
- Document viewer panel visible on the right

---

## Scenario: Create and delete conversation

**Preconditions**: App loaded

**Steps**:
1. Click the "New conversation" button in the sidebar
2. Verify a new conversation appears in the sidebar list
3. Take a screenshot
4. Delete the conversation (via delete button on hover/context)
5. Verify the conversation is removed from the sidebar
6. Take a screenshot

**Expected**:
- Conversation appears immediately after creation
- Conversation disappears after deletion
- No errors in console

---

## Scenario: Upload single document

**Preconditions**: A conversation is selected

**Steps**:
1. Upload a PDF via the upload area (use a test fixture PDF or drag-drop)
2. Wait for upload to complete
3. Take a screenshot

**Expected**:
- Document viewer shows the PDF filename and page count
- PDF content renders in the viewer panel
- Page navigation controls appear at the bottom

---

## Scenario: Upload multiple documents

**Preconditions**: A conversation with one document already uploaded

**Steps**:
1. Upload a second PDF document
2. Wait for upload to complete
3. Take a screenshot

**Expected**:
- Document tabs appear at the top of the viewer (showing both filenames)
- Both documents are selectable
- Active document is highlighted

---

## Scenario: Switch between documents

**Preconditions**: A conversation with 2+ documents uploaded

**Steps**:
1. Click on the second document tab
2. Take a screenshot
3. Click on the first document tab
4. Take a screenshot

**Expected**:
- PDF viewer updates to show the selected document
- Page number resets to 1 when switching
- Active tab styling updates correctly

---

## Scenario: Delete a document

**Preconditions**: A conversation with 2+ documents

**Steps**:
1. Hover over a document tab to reveal the delete (X) button
2. Click the delete button
3. Take a screenshot

**Expected**:
- Document is removed from the tab list
- If the active document was deleted, viewer switches to remaining document
- Tab bar hides if only one document remains (falls back to header-only view)

---

## Scenario: Send message and receive response

**Preconditions**: A conversation with at least one document uploaded

**Steps**:
1. Type a question about the document in the chat input (e.g., "What is this document about?")
2. Send the message
3. Wait for the streaming response to complete
4. Take a screenshot

**Expected**:
- User message appears in the chat as a bubble
- Assistant response streams in progressively
- Response references content from the uploaded document
- Conversation title updates in the sidebar (auto-generated from first message)

---

## Scenario: Multi-document question

**Preconditions**: A conversation with 2+ documents uploaded, at least one prior message

**Steps**:
1. Ask a question that spans both documents (e.g., "Compare the key terms across both documents")
2. Wait for the streaming response to complete
3. Take a screenshot

**Expected**:
- Response references content from multiple documents
- Response identifies documents by name

---

## Scenario: Citations appear in response

**Preconditions**: A conversation with at least one document uploaded

**Steps**:
1. Ask a specific question about the document (e.g., "What is the annual rent in the lease agreement?")
2. Wait for the streaming response to complete
3. Take a screenshot

**Expected**:
- Response contains small blue numbered markers (e.g., 1, 2) inline in the text
- Below the response, citation pills appear showing document name and page number (e.g., "lease-agreement.pdf, p. 3")
- Each pill has a matching number badge on the left
- The numbered markers in the text correspond to the pills below

---

## Scenario: Citation click navigates to page

**Preconditions**: A conversation with a document uploaded and an assistant response with citations

**Steps**:
1. Click on a citation pill below an assistant response
2. Take a screenshot
3. Verify the document viewer state

**Expected**:
- Document viewer switches to the cited document (if multi-doc)
- Document viewer navigates to the cited page number
- The page indicator at the bottom updates to show the correct page

---

## Scenario: Page navigation

**Preconditions**: A document with 2+ pages is displayed in the viewer

**Steps**:
1. Click the "next page" arrow in the viewer
2. Take a screenshot
3. Click the "previous page" arrow
4. Take a screenshot

**Expected**:
- Page number updates (e.g., "Page 2 of 5")
- PDF content changes to show the correct page
- Previous button disabled on page 1, next button disabled on last page
