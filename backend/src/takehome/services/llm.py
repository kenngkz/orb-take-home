from __future__ import annotations

import html
from collections.abc import AsyncIterator

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from takehome.services.retrieval import ChunkResult

MAX_HISTORY_TURNS = 20

agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt=(
        "You are a helpful legal document assistant for commercial real estate lawyers. "
        "You help lawyers review and understand documents during due diligence.\n\n"
        "CITATION FORMAT — MANDATORY:\n"
        "You MUST cite every factual claim using [filename.pdf, page N] format. "
        "The filename MUST be copied exactly from the 'document' attribute of the <chunk> tag — "
        "never use the document's internal title or heading. "
        "Place citations inline immediately after the relevant sentence.\n\n"
        "Example — if you receive:\n"
        '<chunk document="title-report-lot-7.pdf" page="1">Victoria Park Developments Ltd paid £4,250,000.</chunk>\n'
        "Correct: The purchase price was £4,250,000 [title-report-lot-7.pdf, page 1].\n"
        "WRONG: [Source: Official Title Report, Page 1] — never use the document's internal title.\n\n"
        "OTHER INSTRUCTIONS:\n"
        "- Document excerpts are provided in <chunk> tags with 'document' and 'page' attributes.\n"
        "- The user may have uploaded multiple documents. Compare and cross-reference across them.\n"
        "- If the answer is not in the provided excerpts, say so clearly. Do not fabricate information.\n"
        "- Be concise and precise. Lawyers value accuracy over verbosity."
    ),
)


async def generate_title(user_message: str) -> str:
    """Generate a 3-5 word conversation title from the first user message."""
    result = await agent.run(
        f"Generate a concise 3-5 word title for a conversation that starts with: '{user_message}'. "
        "Return only the title, nothing else."
    )
    title = str(result.output).strip().strip('"').strip("'")
    # Truncate if too long
    if len(title) > 100:
        title = title[:97] + "..."
    return title


def _build_context_prompt(chunks: list[ChunkResult]) -> str:
    """Build the document context portion of the prompt."""
    if not chunks:
        return (
            "No documents have been uploaded yet. If the user asks about a document, "
            "let them know they need to upload one first."
        )

    chunk_sections: list[str] = []
    for chunk in chunks:
        safe_name = html.escape(chunk.document_filename, quote=True)
        safe_content = html.escape(chunk.content)
        chunk_sections.append(
            f'<chunk document="{safe_name}" page="{chunk.page_number}">\n'
            f"{safe_content}\n</chunk>"
        )
    return (
        "The following are excerpts from the documents being discussed:\n\n"
        "<documents>\n" + "\n".join(chunk_sections) + "\n</documents>"
    )


def _build_message_history(
    conversation_history: list[dict[str, str]],
) -> list[ModelMessage]:
    """Convert conversation history to Pydantic-AI message objects.

    Applies a sliding window to keep only the last MAX_HISTORY_TURNS messages.
    """
    # Apply sliding window
    recent = conversation_history[-MAX_HISTORY_TURNS:]

    messages: list[ModelMessage] = []
    for msg in recent:
        if msg["role"] == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=msg["content"])]))
        elif msg["role"] == "assistant":
            messages.append(ModelResponse(parts=[TextPart(content=msg["content"])]))
    return messages


async def chat_with_documents(
    user_message: str,
    chunks: list[ChunkResult],
    conversation_history: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Stream a response to the user's message, yielding text chunks.

    Builds a prompt with document context, converts conversation history to
    proper role-tagged messages via Pydantic-AI's message_history, and streams
    the response.
    """
    context = _build_context_prompt(chunks)
    history = _build_message_history(conversation_history)

    # Prepend document context to the user message with citation reminder
    user_prompt = (
        f"{context}\n\n"
        "IMPORTANT: Cite every fact using [filename.pdf, page N] — "
        "use the exact filename from the chunk document attribute.\n\n"
        f"{user_message}"
    )

    async with agent.run_stream(user_prompt, message_history=history) as result:
        async for text in result.stream_text(delta=True):
            yield text

