from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import psycopg
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
    Rating
)
from .services import process_video

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/lego-share/uploads")
MODEL_OUTPUT_DIR = os.getenv("MODEL_OUTPUT_DIR", "/tmp/lego-share/models")
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 100_000_000))  # 100MB default

# Ensure directories exist
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(MODEL_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI()

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount static files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/models", StaticFiles(directory=MODEL_OUTPUT_DIR), name="models")

# In-memory storage
creations: dict[str, Creation] = {}
comments: dict[str, list[Comment]] = {}
ratings: dict[str, dict[str, int]] = {}

@app.get("/api/creations", response_model=list[Creation])
async def list_creations():
    return list(creations.values())

@app.post("/api/creations/{creation_id}/comments", response_model=Comment)
async def add_comment(creation_id: str, comment: CommentCreate):
    if creation_id not in creations:
        raise HTTPException(status_code=404, detail="Creation not found")
    
    comment_id = str(uuid.uuid4())
    new_comment = Comment(
        id=comment_id,
        creation_id=creation_id,
        author=comment.author,
        content=comment.content,
        created_at=datetime.now()
    )
    
    if creation_id not in comments:
        comments[creation_id] = []
    comments[creation_id].append(new_comment)
    return new_comment

@app.get("/api/creations/{creation_id}/comments", response_model=list[Comment])
async def get_comments(creation_id: str):
    if creation_id not in creations:
        raise HTTPException(status_code=404, detail="Creation not found")
    return comments.get(creation_id, [])

@app.post("/api/creations/{creation_id}/rate")
async def rate_creation(creation_id: str, rating: Rating):
    if creation_id not in creations:
        raise HTTPException(status_code=404, detail="Creation not found")
    
    if creation_id not in ratings:
        ratings[creation_id] = {}
    
    
    # Store the user's rating
    ratings[creation_id][rating.user_id] = rating.score
    
    # Update the creation's like count (for now, we'll count ratings >= 4 as likes)
    like_count = sum(1 for score in ratings[creation_id].values() if score >= 4)
    creations[creation_id].likes = like_count
    
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
        if video_id not in creations:
            creation = Creation(
                id=video_id,
                title=f"LEGO Creation {video_id[:8]}",  # Default title
                author="Anonymous",  # Default author
                video_url=video_url,
                images=sorted(images) if images else [],
                model_url=f"/models/{video_id}.obj",
                likes=0,
                created_at=datetime.now()
            )
            creations[video_id] = creation
            comments[video_id] = []  # Initialize empty comments list
            ratings[video_id] = {}   # Initialize empty ratings dict
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
