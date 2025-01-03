import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { VideoPlayer } from '@/components/video-player';
import { CommentSection } from '@/components/comment-section';
import { RatingSection } from '@/components/rating-section';

interface Creation {
  id: string;
  title: string;
  author: string;
  video_url: string;
  images: string[];
  model_url: string;
  likes: number;
  created_at: string;
}

export function CreationList() {
  const [creations, setCreations] = useState<Creation[]>([]);

  useEffect(() => {
    // TODO: Fetch creations from API
    const fetchCreations = async () => {
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL}/api/creations`);
        const data = await response.json();
        setCreations(data);
      } catch (error) {
        console.error('Failed to fetch creations:', error);
      }
    };

    fetchCreations();
  }, []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {creations.map((creation) => (
        <Card key={creation.id}>
          <CardHeader>
            <CardTitle>{creation.title}</CardTitle>
            <p className="text-sm text-muted-foreground">By {creation.author}</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <VideoPlayer src={creation.video_url} />
            <RatingSection creationId={creation.id} initialLikes={creation.likes} />
            <CommentSection creationId={creation.id} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
