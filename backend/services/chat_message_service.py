import json

from sqlalchemy.orm import Session

from database import ChatMessage, ChatSession, get_utc_now


def add_assistant_message(db: Session, chat_id: str, content: str) -> ChatMessage:
    message = ChatMessage(
        chat_id=chat_id,
        role="assistant",
        content=content,
        variants_json=json.dumps([content]),
        active_variant_index=0,
    )
    db.add(message)

    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if chat:
        chat.updated_at = get_utc_now()

    return message
