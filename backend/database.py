import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, event
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import sqlite3

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "not_notebooklm.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30}
)

# Enable WAL mode and synchronous=NORMAL on every new SQLite connection
# WAL (Write-Ahead Logging) allows concurrent reads while writes are in progress
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")  # 30-second lock wait timeout
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4())) # UUID string
    title = Column(String, default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    documents = relationship("Document", back_populates="chat_session")
    messages = relationship("ChatMessage", back_populates="chat_session", order_by="ChatMessage.created_at")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, ForeignKey("chat_sessions.id"))
    filename = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
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
    is_oa = Column(Boolean, nullable=True, default=True)
    access_status = Column(String, nullable=True)
    snippet = Column(Text, nullable=True)
    venue = Column(String, nullable=True)
    citations = Column(Integer, nullable=True, default=0)
    quality_tier = Column(Integer, nullable=True, default=4)
    
    chat_session = relationship("ChatSession", back_populates="documents")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, ForeignKey("chat_sessions.id"))
    role = Column(String) # 'user' or 'assistant'
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    chat_session = relationship("ChatSession", back_populates="messages")

Base.metadata.create_all(bind=engine)

# Auto-migrate columns if missing in SQLite
try:
    with engine.connect() as conn:
        from sqlalchemy import text
        res = conn.execute(text("PRAGMA table_info(chat_sessions)")).fetchall()
        cols = [r[1] for r in res]
        if "updated_at" not in cols:
            conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN updated_at DATETIME"))
            conn.execute(text("UPDATE chat_sessions SET updated_at = created_at WHERE updated_at IS NULL"))
            conn.commit()

        # Auto-migrate Document metadata columns
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
        conn.commit()
except Exception as e:
    print(f"[DB Migration Warning]: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
