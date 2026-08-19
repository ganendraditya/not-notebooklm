from .chats import router as chats_router
from .documents import router as documents_router
from .papers import router as papers_router
from .settings import router as settings_router

__all__ = [
    "chats_router",
    "documents_router",
    "papers_router",
    "settings_router",
]
