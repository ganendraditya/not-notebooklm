import os
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
import re
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base, SessionLocal, Document

from utils.file_utils import UPLOAD_DIR, TEMP_ZIPS_DIR, CHAT_MEDIA_DIR, get_doc_file_path
from utils.pdf_utils import is_binary_pdf
from routers import (
    chats_router,
    messages_router,
    documents_router,
    papers_router,
    settings_router,
    storage_router,
)

logger = logging.getLogger("uvicorn.error")

# Create database tables
Base.metadata.create_all(bind=engine)

import asyncio

def heal_legacy_upload_files():
    """Validates and heals missing or zero-byte metadata files in background without blocking server startup."""
    db = SessionLocal()
    try:
        docs = db.query(Document).all()
        for d in docs:
            existing_path = get_doc_file_path(d.chat_id, d.filename)
            
            # If valid binary PDF exists anywhere on disk, keep it intact
            if os.path.exists(existing_path) and (is_binary_pdf(existing_path) or os.path.getsize(existing_path) >= 35000):
                continue

            # If file doesn't exist or is completely empty (0-byte), write overview metadata fallback
            if not os.path.exists(existing_path) or os.path.getsize(existing_path) == 0:
                clean_title = re.sub(r'<[^>]+>', '', os.path.splitext(d.filename)[0]).replace("_", " ").strip()
                doc_text = f"# {d.title or clean_title} ({d.year or 'N/A'})\n\n"
                if d.doi:
                    doc_text += f"**DOI:** {d.doi}  \n"
                if d.url:
                    doc_text += f"**URL:** {d.url}  \n\n"
                doc_text += f"## Abstract & Overview\n\n{d.abstract or d.snippet or 'Metadata & abstract indexed in workspace.'}\n"
                try:
                    with open(existing_path, "w", encoding="utf-8") as fp:
                        fp.write(doc_text)
                except Exception as e:
                    logger.error(f"[Heal File Error] Failed to write repair file {existing_path}: {e}")
    except Exception as e:
        logger.warning(f"[Heal Task Warning]: {e}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run legacy file repair as non-blocking background task so server binds instantly
    asyncio.create_task(asyncio.to_thread(heal_legacy_upload_files))
    yield

app = FastAPI(title="Not-NotebookLM API", lifespan=lifespan)

# Secure static mount: expose only chat media attachments (images/thumbnails)
# Research documents and ZIP downloads are protected and served exclusively via validated endpoints
os.makedirs(CHAT_MEDIA_DIR, exist_ok=True)
app.mount("/uploads/chat_media", StaticFiles(directory=CHAT_MEDIA_DIR), name="chat_media")

# Setup secure and explicit CORS configuration
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
if allowed_origins_env:
    allowed_origins = [orig.strip() for orig in allowed_origins_env.split(",") if orig.strip()]
else:
    # Default trusted local development origins (Never default to wildcard in production)
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

# Only enable wildcard if explicitly configured by developer in env
is_wildcard = allowed_origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=not is_wildcard,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Range", "Origin", "X-Requested-With"],
)

# Include Routers
app.include_router(chats_router)
app.include_router(messages_router)
app.include_router(documents_router)
app.include_router(papers_router)
app.include_router(settings_router)
app.include_router(storage_router)

@app.get("/")
def root():
    return {"status": "ok", "app": "Not-NotebookLM API"}
