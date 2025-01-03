import { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Star } from 'lucide-react';

interface RatingSectionProps {
  creationId: string;
  initialLikes?: number;
}

export function RatingSection({ creationId, initialLikes = 0 }: RatingSectionProps) {
  const [rating, setRating] = useState(0);
  const [likes, setLikes] = useState(initialLikes);
  const [userId] = useState('user-' + Math.random().toString(36).substr(2, 9)); // TODO: Implement user system

  const handleRate = async (score: number) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/creations/${creationId}/rate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ creation_id: creationId, user_id: userId, score }),
      });

      if (response.ok) {
        setRating(score);
        // Update likes if rating is >= 4
        if (score >= 4) {
          setLikes(prev => prev + 1);
        }
      }
    } catch (error) {
      console.error('Failed to submit rating:', error);
    }
  };

  return (
    <Card>
      <CardHeader>
        <h3 className="text-lg font-semibold">Rate this creation</h3>
      </CardHeader>
      <CardContent>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((score) => (
            <Button
              key={score}
              variant={rating >= score ? "default" : "outline"}
              size="sm"
              onClick={() => handleRate(score)}
            >
              <Star className={rating >= score ? "fill-current" : ""} size={16} />
            </Button>
          ))}
        </div>
        <p className="text-sm text-muted-foreground mt-2">{likes} likes</p>
      </CardContent>
    </Card>
  );
}
