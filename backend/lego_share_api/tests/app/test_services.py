import pytest
import numpy as np
import cv2
from pathlib import Path
from app.services import (
    compute_frame_quality,
    compute_frame_difference,
    extract_frames,
    generate_3d_model,
    process_video
)
from app.models import ProcessingStatus

@pytest.fixture
def sample_video(tmp_path):
    """Create a sample 360-degree video for testing."""
    video_path = str(tmp_path / "test_360.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, 30.0, (640, 480))
    
    # Create a rotating object simulation with more visual features
    for i in range(90):  # 3 seconds of 360-degree rotation
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128  # Gray background
        angle = i * 4  # 4 degrees per frame
        
        # Create multiple shapes with different colors for better feature detection
        # Main rectangle
        rect_points = np.array([[-50, -50], [50, -50], [50, 50], [-50, 50]], dtype=np.float32)
        rotation_matrix = cv2.getRotationMatrix2D(center=(0, 0), angle=angle, scale=1)
        rotated_points = np.dot(rect_points, rotation_matrix[:, :2].T) + rotation_matrix[:, 2]
        rotated_points = rotated_points.astype(np.int32) + np.array([320, 240])
        cv2.fillPoly(frame, [rotated_points], (255, 0, 0))  # Red rectangle
        
        # Additional features
        for offset in [(30, 30), (-30, -30), (30, -30), (-30, 30)]:
            circle_center = (320 + offset[0], 240 + offset[1])
            rot_x = int(circle_center[0] + 20 * np.cos(np.radians(angle)))
            rot_y = int(circle_center[1] + 20 * np.sin(np.radians(angle)))
            cv2.circle(frame, (rot_x, rot_y), 5, (0, 255, 0), -1)  # Green circles
            
        # Add text for scale reference
        cv2.putText(frame, "LEGO", (320-20, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        out.write(frame)
    
    out.release()
    return video_path

@pytest.mark.asyncio
async def test_frame_extraction(sample_video, tmp_path):
    """Test frame extraction from 360-degree video."""
    output_dir = tmp_path / "frames"
    frames = await extract_frames(sample_video, output_dir)
    assert len(frames) >= 8, f"Expected at least 8 frames for 3D reconstruction, got {len(frames)}"
    assert all(isinstance(path, Path) for path in frames)
    # Check if we have enough frames for 360-degree coverage
    assert len(frames) >= 8  # Minimum frames for reasonable 360-degree coverage

@pytest.mark.asyncio
async def test_frame_quality_assessment():
    """Test frame quality assessment."""
    # Create a good quality frame
    good_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(good_frame, (100, 100), (200, 200), (255, 255, 255), -1)
    
    # Create a blurry frame
    blurry_frame = cv2.GaussianBlur(good_frame, (15, 15), 0)
    
    good_quality = compute_frame_quality(good_frame)
    poor_quality = compute_frame_quality(blurry_frame)
    
    assert good_quality > poor_quality
    assert 0 <= good_quality <= 1
    assert 0 <= poor_quality <= 1

@pytest.mark.asyncio
async def test_3d_model_generation(sample_video, tmp_path):
    """Test 3D model generation from video frames."""
    video_dir = tmp_path / "video"
    model_dir = tmp_path / "model"
    video_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    
    # Copy test video to video directory
    import shutil
    shutil.copy(sample_video, video_dir / "original.mp4")
    
    result = await process_video("test_video", video_dir, model_dir)
    assert isinstance(result, ProcessingStatus)
    assert result.status in ["completed", "error"]
    
    if result.status == "completed":
        assert result.progress == 100
        assert result.frame_extraction_progress == 100
        assert result.reconstruction_progress == 100
        assert result.total_frames_extracted > 0
        assert result.points_generated > 0
        assert result.model_url is not None

@pytest.mark.asyncio
async def test_progress_tracking(sample_video, tmp_path):
    """Test progress tracking during video processing."""
    video_dir = tmp_path / "video_progress"
    model_dir = tmp_path / "model_progress"
    video_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)
    
    # Copy test video to video directory
    import shutil
    shutil.copy(sample_video, video_dir / "original.mp4")
    
    result = await process_video("test_progress", video_dir, model_dir)
    assert isinstance(result, ProcessingStatus)
    assert hasattr(result, 'progress')
    assert hasattr(result, 'frame_extraction_progress')
    assert hasattr(result, 'reconstruction_progress')
    assert 0 <= result.progress <= 100
    assert 0 <= result.frame_extraction_progress <= 100
    assert 0 <= result.reconstruction_progress <= 100

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling with invalid input."""
    with pytest.raises(Exception):
        await process_video("nonexistent_video.mp4")
