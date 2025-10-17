from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: int
    username: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ChangeCredentialsRequest(BaseModel):
    current_password: str
    new_username: str = Field(min_length=3)
    new_password: str = Field(min_length=6)


class ProductCreate(BaseModel):
    sku: str
    manufacturer: str
    title: Optional[str] = None
    search_mode: Optional[str] = Field(default=None, description="google|openai")


class ProductRead(BaseModel):
    id: int
    sku: str
    manufacturer: str
    title: Optional[str]
    search_mode: Optional[str]
    status: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ImageResultRead(BaseModel):
    id: int
    provider: str
    image_url: str
    thumbnail_url: Optional[str]
    is_selected: bool

    class Config:
        orm_mode = True


class ProductDetail(ProductRead):
    images: List[ImageResultRead]


class SearchRequest(BaseModel):
    mode: str
    query_override: Optional[str] = None


class BatchSearchRequest(BaseModel):
    product_ids: List[int]
    mode: str
    query_override: Optional[str] = None


class SelectImageRequest(BaseModel):
    image_id: int


class LogEntry(BaseModel):
    id: int
    provider: str
    status: str
    request_payload: Optional[str]
    response_payload: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True
