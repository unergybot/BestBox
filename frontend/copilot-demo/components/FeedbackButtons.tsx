'use client';

import { useState } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';

interface FeedbackButtonsProps {
  messageId: string;
  sessionId: string;
  onFeedbackSubmitted?: (rating: 'positive' | 'negative') => void;
}

export function FeedbackButtons({
  messageId,
  sessionId,
  onFeedbackSubmitted
}: FeedbackButtonsProps) {
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFeedback = async (rating: 'positive' | 'negative') => {
    if (feedback) return; // Already submitted

    setIsSubmitting(true);

    try {
      const response = await fetch('http://localhost:8000/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message_id: messageId,
          session_id: sessionId,
          rating: rating
        })
      });

      if (!response.ok) {
        throw new Error('Failed to submit feedback');
      }

      setFeedback(rating);
      onFeedbackSubmitted?.(rating);

    } catch (error) {
      console.error('Failed to submit feedback:', error);
      alert('Failed to submit feedback. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex items-center gap-2 mt-2">
      <button
        onClick={() => handleFeedback('positive')}
        disabled={isSubmitting || feedback !== null}
        className={`p-1.5 rounded-md transition-all ${
          feedback === 'positive'
            ? 'bg-green-100 text-green-700 ring-2 ring-green-300'
            : 'hover:bg-gray-100 text-gray-500 hover:text-gray-700'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
        aria-label="Good response"
        title="This response was helpful"
      >
        <ThumbsUp size={16} className={feedback === 'positive' ? 'fill-current' : ''} />
      </button>

      <button
        onClick={() => handleFeedback('negative')}
        disabled={isSubmitting || feedback !== null}
        className={`p-1.5 rounded-md transition-all ${
          feedback === 'negative'
            ? 'bg-red-100 text-red-700 ring-2 ring-red-300'
            : 'hover:bg-gray-100 text-gray-500 hover:text-gray-700'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
        aria-label="Bad response"
        title="This response was not helpful"
      >
        <ThumbsDown size={16} className={feedback === 'negative' ? 'fill-current' : ''} />
      </button>

      {feedback && (
        <span className="text-xs text-gray-500 ml-2 animate-fade-in">
          Thank you for your feedback!
        </span>
      )}
    </div>
  );
}
