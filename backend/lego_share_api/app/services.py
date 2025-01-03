import cv2
import numpy as np
from pathlib import Path
import asyncio
from typing import List, Tuple
import logging
from scipy.spatial.transform import Rotation
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.spatial import cKDTree
import json

logger = logging.getLogger(__name__)

def compute_frame_quality(frame: np.ndarray) -> float:
    """Compute frame quality based on blur and lighting."""
    # Convert to grayscale if needed
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
        
    # Compute blur score using Laplacian variance
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Compute lighting score using average brightness
    brightness_score = np.mean(gray)
    
    # Normalize scores more leniently
    # Blur score: typical values range from 0-1000, normalize to 0-1
    norm_blur = min(1.0, blur_score / 100.0)  # More lenient normalization
    
    # Brightness score: normalize to 0-1, but favor middle range (avoid too dark or too bright)
    norm_brightness = 1.0 - abs((brightness_score - 128) / 128)  # Peak at middle gray
    
    # Combine scores with weighted average
    quality_score = (0.7 * norm_blur + 0.3 * norm_brightness)
    
    logger.debug(f"Frame quality: blur={blur_score:.2f}, brightness={brightness_score:.2f}, quality={quality_score:.4f}")
    return quality_score

def compute_frame_difference(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """Compute difference between two frames using absolute difference."""
    # Convert to grayscale if needed
    if len(frame1.shape) == 3:
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    else:
        gray1, gray2 = frame1, frame2
    
    # Apply Gaussian blur to reduce noise
    gray1_blur = cv2.GaussianBlur(gray1, (5, 5), 0)
    gray2_blur = cv2.GaussianBlur(gray2, (5, 5), 0)
    
    # Compute absolute difference and normalize
    diff = cv2.absdiff(gray1_blur, gray2_blur)
    norm_diff = np.mean(diff) / 255.0  # Normalize to 0-1 range
    
    logger.debug(f"Frame difference: {norm_diff:.4f}")
    return float(norm_diff)

async def extract_frames(video_path: Path, output_dir: Path, min_quality: float = 0.5, min_difference: float = 0.001) -> List[Path]:
    """Extract high-quality frames with significant viewpoint changes.
    
    Args:
        video_path: Path to the input video file
        output_dir: Directory to save extracted frames
        min_quality: Minimum quality threshold (0-1), default 0.5 to ensure good but not overly strict quality
        min_difference: Minimum difference threshold (0-1) for frame-to-frame comparison, default 0.001
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_paths = []
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("Error opening video file")
    
    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        last_saved_frame = None
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Compute frame quality
            quality = compute_frame_quality(frame)
            logger.info(f"Frame {frame_count}: quality={quality:.4f}")
            
            # Check if frame is good enough quality
            if quality > min_quality:
                # Calculate frame difference if we have a previous saved frame
                frame_diff = 0.0
                if last_saved_frame is not None:
                    frame_diff = compute_frame_difference(frame, last_saved_frame)
                    logger.debug(f"Frame {frame_count}: Comparing with last saved frame - diff={frame_diff:.4f}")
                
                # For first frame or if significant difference from last saved frame
                if last_saved_frame is None or frame_diff > min_difference:
                    frame_path = output_dir / f"frame_{len(frame_paths):04d}.jpg"
                    cv2.imwrite(str(frame_path), frame)
                    frame_paths.append(frame_path)
                    last_saved_frame = frame.copy()
                    
                    # Log progress and frame info
                    progress = (frame_count / total_frames) * 100
                    logger.info(f"Frame {len(frame_paths)-1} saved (frame_count={frame_count}, "
                              f"quality={quality:.4f}, diff={frame_diff:.4f}, "
                              f"progress={progress:.1f}%)")
                else:
                    logger.debug(f"Frame {frame_count}: Skipped - quality={quality:.4f} (>{min_quality}), "
                               f"but diff={frame_diff:.4f} (<={min_difference})")
            else:
                logger.debug(f"Frame {frame_count}: Skipped - quality={quality:.4f} (<={min_quality})")
            
            frame_count += 1
            
            # Allow other tasks to run
            if frame_count % 30 == 0:  # More frequent yields for responsiveness
                await asyncio.sleep(0)
    
    finally:
        cap.release()
    
    if not frame_paths:
        raise RuntimeError("No suitable frames found in video")
    
    logger.info(f"Extracted {len(frame_paths)} high-quality frames")
    return frame_paths

def detect_and_match_features(img1: np.ndarray, img2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Detect and match features between two images using SIFT."""
    sift = cv2.SIFT_create()
    
    # Detect keypoints and compute descriptors
    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)
    
    # Match features using FLANN
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(des1, des2, k=2)
    
    # Apply Lowe's ratio test
    good_matches = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good_matches.append(m)
    
    # Get matching points
    pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])
    
    return pts1, pts2

def estimate_camera_pose(pts1: np.ndarray, pts2: np.ndarray, K: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Estimate relative camera pose using essential matrix."""
    E, mask = cv2.findEssentialMat(pts1, pts2, K, method=cv2.RANSAC, prob=0.999, threshold=1.0)
    _, R, t, _ = cv2.recoverPose(E, pts1, pts2, K, mask=mask)
    return R, t

def triangulate_points(pts1: np.ndarray, pts2: np.ndarray, P1: np.ndarray, P2: np.ndarray) -> np.ndarray:
    """Triangulate 3D points from corresponding image points and camera matrices."""
    points_4d = cv2.triangulatePoints(P1, P2, pts1.T, pts2.T)
    points_3d = points_4d[:3] / points_4d[3]
    return points_3d.T

async def generate_3d_model(frame_paths: List[Path], output_path: Path) -> Tuple[int, List[dict]]:
    """Generate a 3D model from extracted frames using Structure from Motion.
    Returns:
        Tuple[int, List[dict]]: Number of points generated and list of camera poses
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Camera intrinsic matrix (approximate values, should be calibrated for better results)
    K = np.array([[1000, 0, 960],
                  [0, 1000, 540],
                  [0, 0, 1]])
    
    # Initialize 3D points and camera poses
    all_points_3d = []
    camera_poses = []
    
    # Process consecutive frame pairs
    for i in range(len(frame_paths) - 1):
        # Read frames
        img1 = cv2.imread(str(frame_paths[i]), cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(str(frame_paths[i + 1]), cv2.IMREAD_GRAYSCALE)
        
        if img1 is None or img2 is None:
            continue
            
        # Detect and match features
        pts1, pts2 = detect_and_match_features(img1, img2)
        
        
        if len(pts1) < 8:  # Minimum points needed for essential matrix
            continue
            
        # Estimate camera pose
        R, t = estimate_camera_pose(pts1, pts2, K)
        
        # First camera matrix (identity rotation and zero translation)
        P1 = np.dot(K, np.hstack((np.eye(3), np.zeros((3, 1)))))
        # Second camera matrix (estimated R and t)
        P2 = np.dot(K, np.hstack((R, t)))
        
        # Triangulate points
        points_3d = triangulate_points(pts1, pts2, P1, P2)
        
        # Filter points by reprojection error
        valid_points = np.abs(points_3d[:, 2]) < 100  # Remove points too far away
        points_3d = points_3d[valid_points]
        
        all_points_3d.extend(points_3d.tolist())
        camera_poses.append({'R': R.tolist(), 't': t.tolist()})
        
        # Allow other tasks to run
        if i % 5 == 0:
            await asyncio.sleep(0)
    
    # Save point cloud as OBJ file
    with open(output_path, 'w') as f:
        # Write vertices
        for point in all_points_3d:
            f.write(f"v {point[0]} {point[1]} {point[2]}\n")
        
        # Save camera poses in a separate JSON file
        poses_path = output_path.parent / f"{output_path.stem}_cameras.json"
        with open(poses_path, 'w') as poses_file:
            json.dump(camera_poses, poses_file)
    
    logger.info(f"Generated 3D model with {len(all_points_3d)} points")
    return len(all_points_3d), camera_poses

from .models import ProcessingStatus

async def update_processing_status(video_id: str, status_data: dict):
    """Update processing status in the database."""
    logger.info(f"Processing status update for {video_id}: {status_data}")
    return status_data

async def process_video(video_id: str, video_dir: Path, model_dir: Path) -> ProcessingStatus:
    """Process uploaded video: extract frames and generate 3D model."""
    status = ProcessingStatus(
        video_id=video_id,
        status="processing",
        progress=0.0,
        frame_extraction_progress=0.0,
        reconstruction_progress=0.0,
        total_frames_extracted=0,
        points_generated=0
    )
    
    try:
        # Extract frames
        frames_dir = video_dir / "frames"
        video_path = video_dir / "original.mp4"
        
        # Start frame extraction
        status.status = "extracting_frames"
        status.progress = 25.0
        await update_processing_status(video_id, status.model_dump())
        
        frame_paths = await extract_frames(video_path, frames_dir)
        status.total_frames_extracted = len(frame_paths)
        status.frame_extraction_progress = 100.0
        status.progress = 50.0
        await update_processing_status(video_id, status.model_dump())
        
        if not frame_paths:
            raise RuntimeError("No suitable frames were extracted from the video")
        
        # Generate 3D model
        status.status = "generating_model"
        status.progress = 75.0
        await update_processing_status(video_id, status.model_dump())
        
        model_path = model_dir / f"{video_id}.obj"
        num_points, camera_poses = await generate_3d_model(frame_paths, model_path)
        
        # Update final status
        status.status = "completed"
        status.progress = 100.0
        status.reconstruction_progress = 100.0
        status.points_generated = num_points
        status.video_url = f"/videos/{video_id}/original.mp4"
        status.images = [str(p.relative_to(video_dir)) for p in frame_paths]
        status.model_url = f"/models/{video_id}.obj"
        
        logger.info(f"Video processing completed for {video_id}")
        await update_processing_status(video_id, status.model_dump())
        return status
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing video {video_id}: {error_msg}")
        status.status = "error"
        status.error_message = error_msg
        await update_processing_status(video_id, status.model_dump())
        return status
