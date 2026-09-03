import asyncio
import json
import logging
from typing import Callable, Awaitable, Any, AsyncGenerator, Optional, Dict
from fastapi.responses import StreamingResponse

logger = logging.getLogger("uvicorn.error")

class SSEStreamEmitter:
    """Helper context passed into streaming workers to emit typed SSE events."""
    def __init__(self, queue: asyncio.Queue):
        self._queue = queue

    async def emit_status(self, text: str):
        """Emits an intermediate thinking / status update to the client."""
        await self._queue.put({"type": "status", "text": text, "data": text})

    async def emit_event(self, event_data: dict):
        """Emits a custom structured event payload."""
        await self._queue.put(event_data)

    async def emit_error(self, err_msg: str, fallback_message: Optional[Dict[str, Any]] = None):
        """Emits a structured error event."""
        payload = {"type": "error", "data": err_msg}
        if fallback_message:
            payload["message"] = fallback_message
        await self._queue.put(payload)

    async def emit_done(self, final_text: str, message_payload: Optional[Dict[str, Any]] = None, **extra):
        """Emits the final completion event."""
        payload = {"type": "done", "data": final_text, **extra}
        if message_payload:
            payload["message"] = message_payload
        await self._queue.put(payload)


def create_sse_stream_response(
    worker_fn: Callable[[SSEStreamEmitter], Awaitable[None]]
) -> StreamingResponse:
    """
    Standardized, DRY Server-Sent Events (SSE) stream handler.
    Handles queue lifecycle, worker task cancellation, JSON serialization, and error wrapping.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue = asyncio.Queue()
        emitter = SSEStreamEmitter(queue)

        async def runner():
            try:
                await worker_fn(emitter)
            except asyncio.CancelledError:
                logger.debug("[SSE Stream Task Cancelled by Client]")
                raise
            except Exception as e:
                logger.error(f"[SSE Stream Worker Uncaught Error]: {e}", exc_info=True)
                await emitter.emit_error(str(e))
            finally:
                await queue.put(None)

        worker_task = asyncio.create_task(runner())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        except asyncio.CancelledError:
            if not worker_task.done():
                worker_task.cancel()
            raise
        finally:
            if not worker_task.done():
                worker_task.cancel()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
