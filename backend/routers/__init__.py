from .chats import router as chats_router
from .messages import router as messages_router
from .documents import router as documents_router
from .papers import router as papers_router
from .settings import router as settings_router
from .storage import router as storage_router

__all__ = [
    "chats_router",
    "messages_router",
    "documents_router",
    "papers_router",
    "settings_router",
    "storage_router",
]
