import os
import uuid
import logging
import time
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, event
from sqlalchemy.orm import Session, sessionmaker, relationship, declarative_base
from sqlalchemy.exc import OperationalError
import sqlite3

logger = logging.getLogger("uvicorn.error")

def get_utc_now():
    return datetime.now(timezone.utc)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "not_notebooklm.db"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

if DATABASE_URL.startswith("sqlite"):
    raw_path = DATABASE_URL.replace("sqlite:///", "")
    if raw_path and not raw_path.startswith(":memory:"):
        parent_dir = os.path.dirname(os.path.abspath(raw_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30}
    )

    # Enable WAL mode and synchronous=NORMAL on every new SQLite connection
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")  # 30-second lock wait timeout
            cursor.close()
else:
    # PostgreSQL / MySQL enterprise connection pool
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4())) # UUID string
    title = Column(String, default="New Chat")
    is_pinned = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)
    
    documents = relationship("Document", back_populates="chat_session")
    messages = relationship("ChatMessage", back_populates="chat_session", order_by="ChatMessage.created_at")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, ForeignKey("chat_sessions.id"), index=True)
    filename = Column(String, index=True)
    created_at = Column(DateTime, default=get_utc_now)
    
    # Persistent metadata (populated at import time, never overwritten by re-parsing)
    title = Column(Text, nullable=True)
    authors = Column(Text, nullable=True)       # JSON string: ["Author A", "Author B"]
    year = Column(String, nullable=True)
    journal = Column(String, nullable=True)
    journal_metric = Column(String, nullable=True)
    doi = Column(String, nullable=True)
    url = Column(String, nullable=True)
    pdf_url = Column(String, nullable=True)
    abstract = Column(Text, nullable=True)
    abstract_type = Column(String, nullable=True)  # "official" or "ai_summary"
    is_oa = Column(Boolean, nullable=True, default=None)
    access_status = Column(String, nullable=True)
    snippet = Column(Text, nullable=True)
    venue = Column(String, nullable=True)
    citations = Column(Integer, nullable=True, default=0)
    quality_tier = Column(Integer, nullable=True, default=4)
    
    chat_session = relationship("ChatSession", back_populates="documents")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, ForeignKey("chat_sessions.id"), index=True)
    role = Column(String) # 'user' or 'assistant'
    content = Column(Text)
    attachments_json = Column(Text, nullable=True) # store attachments JSON
    variants_json = Column(Text, nullable=True) # JSON list of string variants [v1, v2, ...]
    active_variant_index = Column(Integer, default=0, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    
    chat_session = relationship("ChatSession", back_populates="messages")

Base.metadata.create_all(bind=engine)

def auto_migrate_schema():
    """Lightweight schema migrator for SQLite columns."""
    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            
            # ChatSessions
            res = conn.execute(text("PRAGMA table_info(chat_sessions)")).fetchall()
            cols = [r[1] for r in res]
            if "updated_at" not in cols:
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN updated_at DATETIME"))
                conn.execute(text("UPDATE chat_sessions SET updated_at = created_at WHERE updated_at IS NULL"))
            if "is_pinned" not in cols:
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN is_pinned BOOLEAN DEFAULT 0"))

            # Documents
            res_docs = conn.execute(text("PRAGMA table_info(documents)")).fetchall()
            doc_cols = [r[1] for r in res_docs]
            new_doc_columns = {
                "title": "TEXT",
                "authors": "TEXT",
                "year": "VARCHAR",
                "journal": "VARCHAR",
                "journal_metric": "VARCHAR",
                "doi": "VARCHAR",
                "url": "VARCHAR",
                "pdf_url": "VARCHAR",
                "abstract": "TEXT",
                "abstract_type": "VARCHAR",
                "is_oa": "BOOLEAN",
                "access_status": "VARCHAR",
                "snippet": "TEXT",
                "venue": "VARCHAR",
                "citations": "INTEGER DEFAULT 0",
                "quality_tier": "INTEGER DEFAULT 4",
            }
            for col_name, col_type in new_doc_columns.items():
                if col_name not in doc_cols:
                    conn.execute(text(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}"))
            
            # ChatMessages
            res_msgs = conn.execute(text("PRAGMA table_info(chat_messages)")).fetchall()
            msg_cols = [r[1] for r in res_msgs]
            if "attachments_json" not in msg_cols:
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN attachments_json TEXT"))
            if "variants_json" not in msg_cols:
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN variants_json TEXT"))
            if "active_variant_index" not in msg_cols:
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN active_variant_index INTEGER DEFAULT 0"))

            # Ensure foreign key indexes for performance
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_chat_id ON documents (chat_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_messages_chat_id ON chat_messages (chat_id)"))

    except Exception as e:
        logger.warning(f"[DB Migration Warning]: {e}")

auto_migrate_schema()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def commit_with_retry(
    db: Session,
    max_retries: int = 3,
    initial_delay: float = 0.1,
    backoff_factor: float = 2.0
) -> None:
    """
    Commit database transaction with exponential backoff retry on lock / concurrency contention.
    Particularly useful for SQLite when background streams or multiple threads write concurrently.
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            db.commit()
            return
        except (OperationalError, sqlite3.OperationalError) as e:
            err_msg = str(e).lower()
            is_locked = "locked" in err_msg or "busy" in err_msg
            if is_locked and attempt < max_retries - 1:
                logger.warning(
                    f"[DB Lock Contention]: Database is locked or busy. Retrying commit (attempt {attempt + 1}/{max_retries}) in {delay:.2f}s..."
                )
                time.sleep(delay)
                delay *= backoff_factor
                continue
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
