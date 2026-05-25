
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from schemas.chat import ChatRequest
from service.chat_service import stream_chat

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    return StreamingResponse(
        stream_chat(request.query, request.user_id, request.session_id),
        media_type="text/event-stream"
    )