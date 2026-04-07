# backend/app/schemas/server.py
from pydantic import BaseModel, Field, ConfigDict, SecretStr
from typing import Optional
from datetime import datetime

class ServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=50)
    password: Optional[SecretStr] = Field(default=None, max_length=100)
    description: Optional[str] = None
    tags: Optional[str] = Field(default=None, max_length=200)

class ServerCreate(ServerBase):
    pass

class ServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = Field(None, min_length=1, max_length=100)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    description: Optional[str] = None
    tags: Optional[str] = None

class ServerResponse(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    tags: Optional[str] = Field(default=None, max_length=200)
    status: str = "offline"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
