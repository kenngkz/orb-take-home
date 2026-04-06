from __future__ import annotations

import html
import re
from collections.abc import AsyncIterator

from pydantic_ai import Agent

from takehome.services.retrieval import ChunkResult

agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt=(
        "You are a helpful legal document assistant for commercial real estate lawyers. "
        "You help lawyers review and understand documents during due diligence.\n\n"
        "IMPORTANT INSTRUCTIONS:\n"
        "- Answer questions based on the document excerpts provided.\n"
        "- Excerpts are tagged with their source document name and page number.\n"
        "- When referencing specific content, ALWAYS cite the document name and page number "
        "(e.g., 'According to lease-agreement.pdf, page 3, ...').\n"
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


async def chat_with_documents(
    user_message: str,
    chunks: list[ChunkResult],
    conversation_history: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Stream a response to the user's message, yielding text chunks.

    Builds a prompt that includes retrieved document chunks and conversation
    history, then streams the response from the LLM.
    """
    prompt_parts: list[str] = []

    if chunks:
        chunk_sections: list[str] = []
        for chunk in chunks:
            safe_name = html.escape(chunk.document_filename, quote=True)
            safe_content = html.escape(chunk.content)
            chunk_sections.append(
                f'<chunk document="{safe_name}" page="{chunk.page_number}">\n'
                f"{safe_content}\n</chunk>"
            )
        prompt_parts.append(
            "The following are excerpts from the documents being discussed:\n\n"
            "<documents>\n" + "\n".join(chunk_sections) + "\n</documents>\n"
        )
    else:
        prompt_parts.append(
            "No documents have been uploaded yet. If the user asks about a document, "
            "let them know they need to upload one first.\n"
        )

    # Add conversation history
    if conversation_history:
        prompt_parts.append("Previous conversation:\n")
        for msg in conversation_history:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt_parts.append(f"User: {content}\n")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}\n")
        prompt_parts.append("\n")

    # Add the current user message
    prompt_parts.append(f"User: {user_message}")

    full_prompt = "\n".join(prompt_parts)

    async with agent.run_stream(full_prompt) as result:
        async for text in result.stream_text(delta=True):
            yield text


def count_sources_cited(response: str) -> int:
    """Count the number of references to document sections, clauses, pages, etc."""
    patterns = [
        r"section\s+\d+",
        r"clause\s+\d+",
        r"page\s+\d+",
        r"paragraph\s+\d+",
    ]
    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, response, re.IGNORECASE))
    return count
