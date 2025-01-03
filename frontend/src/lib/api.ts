import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL;

export interface VideoUploadResponse {
  video_id: string;
  status: string;
  message: string;
}

export interface ProcessingStatus {
  video_id: string;
  status: string;
  progress: number;
  frame_extraction_progress: number;
  reconstruction_progress: number;
  total_frames_extracted: number;
  points_generated: number;
  video_url: string | null;
  images: string[] | null;
  model_url: string | null;
  error_message: string | null;
}

export const uploadVideo = async (file: File): Promise<VideoUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await axios.post(`${API_URL}/api/upload-video`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

export const getProcessingStatus = async (videoId: string): Promise<ProcessingStatus> => {
  const response = await axios.get(`${API_URL}/api/processing-status/${videoId}`);
  return response.data;
};
