import * as React from 'react';
import { Card, CardContent } from '../components/ui/card';
import { VideoPlayer } from './video-player';
import { CommentSection } from './comment-section';
import { RatingSection } from './rating-section';
import { ModelViewer } from './model-viewer';
import { Progress } from './ui/progress';

interface Creation {
  id: string;
  title: string;
  author: string;
  video_url: string;
  images: string[];
  model_url: string;
  likes: number;
  created_at: string;
  status?: string;
  progress?: number;
  frame_extraction_progress?: number;
  reconstruction_progress?: number;
  total_frames_extracted?: number;
  points_generated?: number;
  error_message?: string;
}

interface CreationViewerProps {
  videoId: string;
}

export function CreationViewer({ videoId }: CreationViewerProps) {
  const [creation, setCreation] = React.useState<Creation | null>(null);

  React.useEffect(() => {
    let pollInterval: NodeJS.Timeout;

    const fetchCreation = async () => {
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL}/api/creations/${videoId}`);
        if (!response.ok) throw new Error('Failed to fetch creation');
        const data = await response.json();
        setCreation(data);

        // Start polling if processing
        if (data.status === "processing") {
          pollInterval = setInterval(async () => {
            const pollResponse = await fetch(`${import.meta.env.VITE_API_URL}/api/creations/${videoId}`);
            if (pollResponse.ok) {
              const updatedData = await pollResponse.json();
              setCreation(updatedData);
              
              // Stop polling when processing is complete or failed
              if (updatedData.status !== "processing") {
                clearInterval(pollInterval);
              }
            }
          }, 5000); // Poll every 5 seconds
        }
      } catch (error) {
        console.error('Error fetching creation:', error);
      }
    };

    if (videoId) {
      fetchCreation();
    }

    // Cleanup interval on unmount
    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [videoId]);

  if (!creation) {
    return <div>Loading...</div>;
  }

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <h2 className="text-2xl font-bold">{creation.title}</h2>
        <p className="text-sm text-gray-500">By {creation.author}</p>
        
        <VideoPlayer src={creation.video_url} />
        
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {creation.images.map((image: string, index: number) => (
            <img
              key={index}
              src={image}
              alt={`View ${index + 1}`}
              className="w-full rounded-lg"
            />
          ))}
        </div>
        
        {creation.status === "processing" && (
          <div className="space-y-4 p-4 border rounded-lg">
            <h3 className="text-lg font-semibold">处理中...</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>总进度</span>
                <span>{creation.progress?.toFixed(1)}%</span>
              </div>
              <Progress value={creation.progress} />
              
              <div className="flex justify-between text-sm">
                <span>帧提取</span>
                <span>{creation.frame_extraction_progress?.toFixed(1)}%</span>
              </div>
              <Progress value={creation.frame_extraction_progress} />
              
              <div className="flex justify-between text-sm">
                <span>3D重建</span>
                <span>{creation.reconstruction_progress?.toFixed(1)}%</span>
              </div>
              <Progress value={creation.reconstruction_progress} />
              
              {(creation.total_frames_extracted ?? 0) > 0 && (
                <p className="text-sm text-gray-600">
                  已提取 {creation.total_frames_extracted} 帧
                </p>
              )}
            </div>
          </div>
        )}
        
        {creation.status === "error" && (
          <div className="p-4 border border-red-200 bg-red-50 rounded-lg">
            <h3 className="text-lg font-semibold text-red-600">处理失败</h3>
            <p className="text-sm text-red-500">{creation.error_message}</p>
          </div>
        )}
        
        {creation.status === "completed" && creation.model_url && (
          <ModelViewer modelUrl={creation.model_url} />
        )}
        
        <RatingSection creationId={creation.id} initialLikes={creation.likes} />
        <CommentSection creationId={creation.id} />
      </CardContent>
    </Card>
  );
}
