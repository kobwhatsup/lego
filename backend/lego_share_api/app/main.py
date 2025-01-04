from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
import uuid
from pathlib import Path
import cv2
import numpy as np
from dotenv import load_dotenv
import logging
from datetime import datetime
from .models import (
    VideoUploadResponse, 
    ProcessingStatus,
    Creation,
    CreationCreate,
    Comment,
    CommentCreate,
    Rating,
    # Database models
    DBCreation,
    DBComment,
    DBRating,
    DBCreationImage
)
from .database import get_db, engine, Base
from .services import process_video

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/lego-share/uploads")
MODEL_OUTPUT_DIR = os.getenv("MODEL_OUTPUT_DIR", "/tmp/lego-share/models")
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 100_000_000))  # 100MB default

# Create database tables
Base.metadata.create_all(bind=engine)

# Ensure directories exist
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(MODEL_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI()

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://lego-share-app-hchp0479.devinapps.com"],  # Allow frontend domain
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount static files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/models", StaticFiles(directory=MODEL_OUTPUT_DIR), name="models")

# No need for in-memory storage as we're using database now

@app.get("/api/creations", response_model=list[Creation])
async def list_creations(db: Session = Depends(get_db)):
    db_creations = db.query(DBCreation).all()
    return [
        Creation(
            id=creation.id,
            title=creation.title,
            author=creation.author,
            video_url=creation.video_url,
            images=[img.image_url for img in creation.images],
            model_url=creation.model_url,
            likes=creation.likes,
            comments=[
                Comment(
                    id=comment.id,
                    creation_id=comment.creation_id,
                    author=comment.author,
                    content=comment.content,
                    created_at=comment.created_at
                ) for comment in creation.comments
            ],
            created_at=creation.created_at
        ) for creation in db_creations
    ]

@app.post("/api/creations/{creation_id}/comments", response_model=Comment)
async def add_comment(creation_id: str, comment: CommentCreate, db: Session = Depends(get_db)):
    db_creation = db.query(DBCreation).filter(DBCreation.id == creation_id).first()
    if not db_creation:
        raise HTTPException(status_code=404, detail="Creation not found")
    
    comment_id = str(uuid.uuid4())
    db_comment = DBComment(
        id=comment_id,
        creation_id=creation_id,
        author=comment.author,
        content=comment.content,
        created_at=datetime.utcnow()
    )
    
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    return Comment(
        id=db_comment.id,
        creation_id=db_comment.creation_id,
        author=db_comment.author,
        content=db_comment.content,
        created_at=db_comment.created_at
    )

@app.get("/api/creations/{creation_id}/comments", response_model=list[Comment])
async def get_comments(creation_id: str, db: Session = Depends(get_db)):
    db_creation = db.query(DBCreation).filter(DBCreation.id == creation_id).first()
    if not db_creation:
        raise HTTPException(status_code=404, detail="Creation not found")
    
    return [
        Comment(
            id=comment.id,
            creation_id=comment.creation_id,
            author=comment.author,
            content=comment.content,
            created_at=comment.created_at
        ) for comment in db_creation.comments
    ]

@app.post("/api/creations/{creation_id}/rate")
async def rate_creation(creation_id: str, rating: Rating, db: Session = Depends(get_db)):
    db_creation = db.query(DBCreation).filter(DBCreation.id == creation_id).first()
    if not db_creation:
        raise HTTPException(status_code=404, detail="Creation not found")
    
    # Check if user has already rated this creation
    existing_rating = db.query(DBRating).filter(
        DBRating.creation_id == creation_id,
        DBRating.user_id == rating.user_id
    ).first()
    
    if existing_rating:
        existing_rating.score = rating.score
    else:
        db_rating = DBRating(
            id=str(uuid.uuid4()),
            creation_id=creation_id,
            user_id=rating.user_id,
            score=rating.score
        )
        db.add(db_rating)
    
    # Update creation's like count (ratings >= 4 count as likes)
    like_count = db.query(DBRating).filter(
        DBRating.creation_id == creation_id,
        DBRating.score >= 4
    ).count()
    
    db_creation.likes = like_count
    db.commit()
    
    return {"message": "Rating submitted successfully"}

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.post("/api/upload-video", response_model=VideoUploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    # Validate video content type
    content_type = getattr(file, 'content_type', '')
    if not content_type or not content_type.startswith('video/'):
        raise HTTPException(status_code=400, detail="File must be a video")
    
    # Generate unique ID for this upload
    video_id = str(uuid.uuid4())
    video_dir = Path(UPLOAD_DIR) / video_id
    video_dir.mkdir(parents=True, exist_ok=True)
    
    # Save video file
    video_path = video_dir / "original.mp4"
    try:
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail="File too large")
        
        with open(video_path, "wb") as f:
            f.write(content)
            
        # Start processing in background
        background_tasks.add_task(
            process_video,
            video_id,
            video_dir,
            Path(MODEL_OUTPUT_DIR)
        )
            
    except Exception as e:
        logging.error(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    return VideoUploadResponse(
        video_id=video_id,
        status="uploaded",
        message="Video uploaded successfully. Processing will begin shortly."
    )

@app.get("/api/processing-status/{video_id}", response_model=ProcessingStatus)
async def get_processing_status(video_id: str):
    video_dir = Path(UPLOAD_DIR) / video_id
    if not video_dir.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check for processed files
    video_url = f"/uploads/{video_id}/original.mp4"
    images_dir = video_dir / "frames"
    model_path = Path(MODEL_OUTPUT_DIR) / f"{video_id}.obj"
    
    # Get list of extracted frames if they exist
    images = []
    if images_dir.exists():
        images = [f"/uploads/{video_id}/frames/{f.name}" for f in images_dir.glob("*.jpg")]
    
    # Determine processing status
    if model_path.exists():
        status = "completed"
        progress = 1.0
        
        # Create a Creation object if it doesn't exist yet
        db = next(get_db())
        db_creation = db.query(DBCreation).filter(DBCreation.id == video_id).first()
        if not db_creation:
            db_creation = DBCreation(
                id=video_id,
                title=f"LEGO Creation {video_id[:8]}",  # Default title
                author="Anonymous",  # Default author
                video_url=video_url,
                model_url=f"/models/{video_id}.obj",
                likes=0,
                created_at=datetime.utcnow()
            )
            db.add(db_creation)
            
            # Add images
            for idx, image_url in enumerate(sorted(images) if images else []):
                db_image = DBCreationImage(
                    id=str(uuid.uuid4()),
                    creation_id=video_id,
                    image_url=image_url,
                    order=idx
                )
                db.add(db_image)
            
            db.commit()
    elif images:
        status = "processing"
        progress = 0.5
    else: 
        status = "queued"
        progress = 0.0
    
    return ProcessingStatus(
        video_id=video_id,
        status=status,
        progress=progress,
        video_url=video_url,
        images=sorted(images) if images else None,
        model_url=f"/models/{video_id}.obj" if model_path.exists() else None
    )
