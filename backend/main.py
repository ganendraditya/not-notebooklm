import os
import re
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal, Document
from helpers import UPLOAD_DIR, TEMP_ZIPS_DIR
from routers import chats_router, documents_router, papers_router, settings_router
import pdf_exporter

logger = logging.getLogger("uvicorn.error")

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Not-NotebookLM API")

# Setup CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(chats_router)
app.include_router(documents_router)
app.include_router(papers_router)
app.include_router(settings_router)

def heal_legacy_upload_files():
    """Validates and heals zero-byte or corrupt files on startup."""
    db = SessionLocal()
    try:
        docs = db.query(Document).all()
        for d in docs:
            file_path = os.path.join(UPLOAD_DIR, f"{d.chat_id}_{d.filename}")
            needs_repair = False
            
            if not os.path.exists(file_path):
                needs_repair = True
            else:
                sz = os.path.getsize(file_path)
                if sz < 100:
                    needs_repair = True
                elif d.filename.lower().endswith(".pdf") and not pdf_exporter.is_binary_pdf(file_path):
                    needs_repair = True
                    
            if needs_repair:
                clean_title = re.sub(r'<[^>]+>', '', os.path.splitext(d.filename)[0]).replace("_", " ").strip()
                doc_text = f"# {d.title or clean_title} ({d.year or 'N/A'})\n\n"
                if d.doi:
                    doc_text += f"**DOI:** {d.doi}  \n"
                if d.url:
                    doc_text += f"**URL:** {d.url}  \n\n"
                doc_text += f"## Abstract & Overview\n\n{d.abstract or d.snippet or 'Metadata & abstract indexed in workspace.'}\n"
                try:
                    with open(file_path, "w", encoding="utf-8") as fp:
                        fp.write(doc_text)
                except Exception as e:
                    logger.debug(f"[Heal File Warning]: {e}")
    except Exception as e:
        logger.warning(f"[Heal Task Warning]: {e}")
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    heal_legacy_upload_files()
