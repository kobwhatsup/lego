import cv2
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def generate_test_video():
    """Generate a test video simulating a 360-degree view of a Lego model."""
    # Create output directory if it doesn't exist
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up video writer with H.264 codec
    video_path = str(data_dir / "test_360.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"avc1")  # H.264 codec for better compatibility
    out = cv2.VideoWriter(video_path, fourcc, 30.0, (640, 480))
    
    if not out.isOpened():
        logger.error("Failed to create video writer")
        raise RuntimeError("Could not create video writer")
    
    logger.info(f"Creating test video at {video_path}")
    try:
        # Create rotating rectangle to simulate Lego model
        for i in range(90):  # 3 seconds at 30 fps
            frame = np.ones((480, 640, 3), dtype=np.uint8) * 128  # Gray background
            angle = i * 4  # 4 degrees per frame
            
            # Create main rectangle with color
            rect = np.array([[-50, -50], [50, -50], [50, 50], [-50, 50]], dtype=np.float32)
            rot_mat = cv2.getRotationMatrix2D((0, 0), angle, 1)
            rect = np.dot(rect, rot_mat[:, :2].T) + rot_mat[:, 2] + [320, 240]
            rect = rect.astype(np.int32)
            cv2.fillPoly(frame, [rect], (255, 0, 0))  # Red rectangle
            
            # Add multiple feature points with different colors
            for offset, color in [((30, 30), (0, 255, 0)), 
                                ((-30, -30), (0, 0, 255)),
                                ((30, -30), (255, 255, 0)),
                                ((-30, 30), (0, 255, 255))]:
                x = int(320 + offset[0] * np.cos(np.radians(angle)))
                y = int(240 + offset[1] * np.sin(np.radians(angle)))
                cv2.circle(frame, (x, y), 5, color, -1)
            
            # Add text for scale reference
            cv2.putText(frame, "LEGO", (320-20, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            out.write(frame)
            
        logger.info("Video generation completed")
        return video_path
        
    finally:
        out.release()
        
        # Verify the video file was created correctly
        if Path(video_path).exists():
            size = Path(video_path).stat().st_size
            logger.info(f"Video file created: {video_path} ({size} bytes)")
            
            # Verify the video can be opened
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                logger.info("Video file verified - can be opened correctly")
                cap.release()
            else:
                logger.error("Created video file cannot be opened")
                raise RuntimeError("Video file verification failed")
        else:
            logger.error("Video file was not created")
            raise RuntimeError("Video file creation failed")

if __name__ == "__main__":
    generate_test_video()
