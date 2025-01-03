from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class VideoUploadResponse(BaseModel):
    video_id: str
    status: str
    message: str

class ProcessingStatus(BaseModel):
    video_id: str
    status: str
    progress: float
    frame_extraction_progress: float = 0.0
    reconstruction_progress: float = 0.0
    total_frames_extracted: int = 0
    points_generated: int = 0
    video_url: str | None = None
    images: List[str] | None = None
    model_url: str | None = None
    error_message: str | None = None

class Comment(BaseModel):
    id: str
    creation_id: str
    author: str
    content: str
    created_at: datetime

class Creation(BaseModel):
    id: str
    title: str
    author: str
    video_url: str
    images: List[str]
    model_url: str
    likes: int = 0
    comments: List[Comment] = []
    created_at: datetime

class CreationCreate(BaseModel):
    title: str
    author: str

class CommentCreate(BaseModel):
    content: str
    author: str

class Rating(BaseModel):
    creation_id: str
    user_id: str
    score: int  # 1-5 stars
