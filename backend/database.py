import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "not_notebooklm.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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
except Exception as e:
    print(f"[DB Migration Warning]: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
