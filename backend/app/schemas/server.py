# backend/app/schemas/server.py
from pydantic import BaseModel, Field, ConfigDict, SecretStr
from typing import Optional, Literal
from datetime import datetime

REGION_OPTIONS = Literal["私有云", "公司-上层", "公司", "Fit楼", "公有云", "异构"]


class ServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=50)
    password: Optional[SecretStr] = Field(default=None, max_length=100)
    description: Optional[str] = None
    tags: Optional[str] = Field(default=None, max_length=200)
    region: REGION_OPTIONS = Field(default="私有云")

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
    region: Optional[REGION_OPTIONS] = None

class ServerResponse(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    tags: Optional[str] = Field(default=None, max_length=200)
    status: str = "offline"
    region: REGION_OPTIONS = "私有云"
    is_busy: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
