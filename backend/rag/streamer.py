"""
Streaming logic and response parsing for the RAG engine.
"""

import json
import logging
from fastapi.responses import StreamingResponse

logger = logging.getLogger("uvicorn.error")

def parse_sse_stream(text: str, is_finished: bool = False, error: str = None) -> str:
    """Formats LLM response data as Server-Sent Events."""
    if error:
        payload = {"error": error, "is_finished": True}
    else:
        payload = {"content": text, "is_finished": is_finished}
    return f"data: {json.dumps(payload)}\n\n"

async def llm_stream_generator(chat_coroutine):
    """
    Executes a chat coroutine and yields SSE formatted chunks.
    Allows for dynamic processing (e.g. status updates vs real content).
    """
    try:
        # We can implement intermediate yields via report_status if we capture it
        yield parse_sse_stream("Initializing RAG pipeline...", is_finished=False)
        
        # Execute the main generation (this is blocking but we await it)
        # Note: True streaming from LlamaIndex is complex depending on the LLM class. 
        # This fallback sends a single completed chunk.
        response = await chat_coroutine
        
        # We yield the final response block
        yield parse_sse_stream(response, is_finished=True)
    except Exception as e:
        logger.error(f"[Stream Generator Error]: {e}")
        yield parse_sse_stream("", is_finished=True, error=str(e))

def create_streaming_response(chat_coroutine) -> StreamingResponse:
    """Creates a FastAPI StreamingResponse wrapper."""
    return StreamingResponse(
        llm_stream_generator(chat_coroutine),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
