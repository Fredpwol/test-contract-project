from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="User's plain-language business context and request")
    company_name: Optional[str] = Field(None, description="Optional company or product name to include")
    jurisdiction: Optional[str] = Field(None, description="Optional governing law or location context")
    tone: Optional[str] = Field(None, description="Optional tone/style guidance")


class StartSessionRequest(BaseModel):
    system_prompt: Optional[str] = Field(None, description="Override system behavior")
    metadata: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: ChatMessage


class SetDocumentRequest(BaseModel):
    html: str = Field(..., description="The current base HTML document to modify")
    title: Optional[str] = None


