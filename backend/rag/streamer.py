"""
Streaming logic and response parsing for the RAG engine.
"""

import json
import inspect
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
    Executes a chat coroutine or async generator and yields SSE formatted chunks.
    Allows for dynamic real-time processing and progressive token streaming.
    """
    try:
        if inspect.isasyncgen(chat_coroutine):
            async for chunk in chat_coroutine:
                if chunk:
                    yield parse_sse_stream(chunk, is_finished=False)
            yield parse_sse_stream("", is_finished=True)
        else:
            response = await chat_coroutine
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
