import logging
from typing import List
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from rag.prompts import get_general_chat_system_prompt

logger = logging.getLogger("uvicorn.error")

async def handle_general_chat_pipeline(
    query: str,
    formatted_history: List[LlamaChatMessage],
    target_llm,
    report_status
) -> str:
    """Handles general conversational queries and high-level conceptual questions."""
    chat_msgs = [
        LlamaChatMessage(role=MessageRole.SYSTEM, content=get_general_chat_system_prompt()),
        *(formatted_history if formatted_history else []),
        LlamaChatMessage(role=MessageRole.USER, content=query)
    ]
    await report_status("Thinking...")
    resp = await target_llm.achat(chat_msgs)
    return resp.message.content
