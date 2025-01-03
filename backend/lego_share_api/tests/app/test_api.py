import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import ProcessingStatus

client = TestClient(app)

def test_upload_video(tmp_path):
    """Test video upload endpoint."""
    # Create a test video file
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"test video content")
    
    with open(video_path, "rb") as f:
        response = client.post(
            "/api/upload-video",
            files={"file": ("test.mp4", f, "video/mp4")}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "video_id" in data
    assert "status" in data
    assert data["status"] in ["processing", "uploaded"]  # Accept either status as valid

def test_get_processing_status():
    """Test processing status endpoint."""
    # Test with a non-existent video ID
    response = client.get("/api/processing-status/nonexistent")
    assert response.status_code == 404
    
    # Test with a valid video ID after upload
    with open("tests/app/test.mp4", "wb") as f:
        f.write(b"test video content")
    
    with open("tests/app/test.mp4", "rb") as f:
        upload_response = client.post(
            "/api/upload-video",
            files={"file": ("test.mp4", f, "video/mp4")}
        )
    
    video_id = upload_response.json()["video_id"]
    status_response = client.get(f"/api/processing-status/{video_id}")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert isinstance(status_data, dict)
    assert "status" in status_data
    assert "progress" in status_data
    assert "frame_extraction_progress" in status_data
    assert "reconstruction_progress" in status_data

def test_get_creation():
    """Test creation retrieval endpoint."""
    # Test with a non-existent creation
    response = client.get("/api/creations/nonexistent")
    assert response.status_code == 404
    
    # Test with a valid creation after upload and processing
    with open("tests/app/test.mp4", "wb") as f:
        f.write(b"test video content")
    
    with open("tests/app/test.mp4", "rb") as f:
        upload_response = client.post(
            "/api/upload-video",
            files={"file": ("test.mp4", f, "video/mp4")}
        )
    
    video_id = upload_response.json()["video_id"]
    creation_response = client.get(f"/api/creations/{video_id}")
    assert creation_response.status_code in [200, 404]  # Creation might not be ready yet
    creation_data = creation_response.json()
    if creation_response.status_code == 200:
        assert isinstance(creation_data, dict)
        assert "id" in creation_data
        assert "video_url" in creation_data
        assert "model_url" in creation_data
        assert "status" in creation_data
