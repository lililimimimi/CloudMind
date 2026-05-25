# backend/schemas/chat.py
from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str
    user_id: str
    session_id: str