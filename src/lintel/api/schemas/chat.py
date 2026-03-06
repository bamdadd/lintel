"""Chat response models."""


from pydantic import BaseModel


class ChatMessageResponse(BaseModel):
    message_id: str
    user_id: str
    display_name: str | None = None
    role: str
    content: str
    timestamp: str = ""


class ConversationResponse(BaseModel):
    conversation_id: str
    user_id: str
    display_name: str | None = None
    project_id: str | None = None
    created_at: str = ""
    messages: list[ChatMessageResponse] = []
