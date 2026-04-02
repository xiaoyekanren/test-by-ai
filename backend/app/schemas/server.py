# backend/app/schemas/server.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class ServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=50)
    password: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    tags: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = Field(default="test_node")

class ServerCreate(ServerBase):
    pass

class ServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = Field(None, min_length=1, max_length=100)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    role: Optional[str] = None

class ServerResponse(ServerBase):
    id: int
    status: str = "offline"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)