from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Table
from sqlalchemy.orm import relationship
from .database import Base

# SQLAlchemy Models
class DBCreation(Base):
    __tablename__ = "creations"

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255), nullable=False)
    video_url = Column(String(255), nullable=False)
    model_url = Column(String(255))
    likes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    comments = relationship("DBComment", back_populates="creation", cascade="all, delete-orphan")
    ratings = relationship("DBRating", back_populates="creation", cascade="all, delete-orphan")
    images = relationship("DBCreationImage", back_populates="creation", cascade="all, delete-orphan")

class DBComment(Base):
    __tablename__ = "comments"

    id = Column(String(36), primary_key=True)
    creation_id = Column(String(36), ForeignKey("creations.id"))
    author = Column(String(255), nullable=False)
    content = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    creation = relationship("DBCreation", back_populates="comments")

class DBRating(Base):
    __tablename__ = "ratings"

    id = Column(String(36), primary_key=True)
    creation_id = Column(String(36), ForeignKey("creations.id"))
    user_id = Column(String(36), nullable=False)
    score = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    creation = relationship("DBCreation", back_populates="ratings")

class DBCreationImage(Base):
    __tablename__ = "creation_images"

    id = Column(String(36), primary_key=True)
    creation_id = Column(String(36), ForeignKey("creations.id"))
    image_url = Column(String(255), nullable=False)
    order = Column(Integer, default=0)

    # Relationship
    creation = relationship("DBCreation", back_populates="images")

# Pydantic Models for API
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

class CommentBase(BaseModel):
    author: str
    content: str

class CommentCreate(CommentBase):
    pass

class Comment(CommentBase):
    id: str
    creation_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class CreationBase(BaseModel):
    title: str
    author: str

class CreationCreate(CreationBase):
    pass

class Creation(CreationBase):
    id: str
    video_url: str
    images: List[str]
    model_url: str
    likes: int = 0
    comments: List[Comment] = []
    created_at: datetime

    class Config:
        from_attributes = True

class Rating(BaseModel):
    creation_id: str
    user_id: str
    score: int  # 1-5 stars

    class Config:
        from_attributes = True
