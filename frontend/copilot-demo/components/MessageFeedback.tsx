"use client";

import { useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface MessageFeedbackProps {
  sessionId: string;
  messageId?: string;
  agentType?: string;
  compact?: boolean;
}

/**
 * Inline message feedback component with thumbs up/down and optional comment.
 * Sends feedback to POST /api/feedback.
 */
export default function MessageFeedback({
  sessionId,
  messageId,
  agentType,
  compact = false,
}: MessageFeedbackProps) {
  const [submitted, setSubmitted] = useState<"positive" | "negative" | null>(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");
  const [sending, setSending] = useState(false);

  const submit = useCallback(
    async (feedbackType: "positive" | "negative", commentText?: string) => {
      setSending(true);
      try {
        await fetch(`${API_BASE}/api/feedback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            message_id: messageId,
            feedback_type: feedbackType,
            comment: commentText || undefined,
            agent_type: agentType,
          }),
        });
        setSubmitted(feedbackType);
      } catch (err) {
        console.error("Feedback submission failed:", err);
      } finally {
        setSending(false);
      }
    },
    [sessionId, messageId, agentType],
  );

  const handleThumb = (type: "positive" | "negative") => {
    if (submitted) return;
    // Optimistic: mark as submitted immediately
    setSubmitted(type);
    if (type === "negative") {
      setShowComment(true);
    } else {
      submit(type);
    }
  };

  const handleCommentSubmit = () => {
    submit(submitted || "negative", comment);
    setShowComment(false);
  };

  if (submitted && !showComment) {
    return (
      <div className={`flex items-center gap-1 text-xs text-gray-400 ${compact ? "" : "mt-2"}`}>
        {submitted === "positive" ? (
          <svg className="w-3.5 h-3.5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
            <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
          </svg>
        ) : (
          <svg className="w-3.5 h-3.5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
            <path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.106-1.79l-.05-.025A4 4 0 0011.057 2H5.64a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866a4 4 0 00.8-2.4z" />
          </svg>
        )}
        <span>Thanks for the feedback!</span>
      </div>
    );
  }

  return (
    <div className={compact ? "" : "mt-2"}>
      <div className="flex items-center gap-1">
        <button
          onClick={() => handleThumb("positive")}
          disabled={sending}
          className="p-1 rounded hover:bg-green-50 text-gray-400 hover:text-green-600 transition-colors disabled:opacity-50"
          title="Helpful"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6.633 10.5c.806 0 1.533-.446 2.031-1.08a9.041 9.041 0 012.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 00.322-1.672V3a.75.75 0 01.75-.75A2.25 2.25 0 0116.5 4.5c0 1.152-.26 2.243-.723 3.218-.266.558.107 1.282.725 1.282h3.126c1.026 0 1.945.694 2.054 1.715.045.422.068.85.068 1.285a11.95 11.95 0 01-2.649 7.521c-.388.482-.987.729-1.605.729H14.23c-.483 0-.964-.078-1.423-.23l-3.114-1.04a4.501 4.501 0 00-1.423-.23H5.904M14.25 9h2.25M5.904 18.75c.083.205.173.405.27.602.197.4-.078.898-.523.898h-.908c-.889 0-1.713-.518-1.972-1.368a12 12 0 01-.521-3.507c0-1.553.295-3.036.831-4.398C3.387 10.203 4.167 9.75 5 9.75h1.053c.472 0 .745.556.5.96a8.958 8.958 0 00-1.302 4.665c0 1.194.232 2.333.654 3.375z" />
          </svg>
        </button>
        <button
          onClick={() => handleThumb("negative")}
          disabled={sending}
          className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
          title="Not helpful"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 15h2.25m8.024-9.75c.011.05.028.1.052.148.591 1.2.924 2.55.924 3.977a8.96 8.96 0 01-1.302 4.666c-.245.403.028.959.5.959h1.053c.832 0 1.612-.453 1.918-1.227C20.705 12.41 21 10.836 21 9.188c0-1.553-.295-3.036-.831-4.398C19.836 4.103 19.056 3.75 18.224 3.75h-.908c-.446 0-.72.498-.523.898.197.4.369.797.465 1.207M7.5 15H5.904c-.472 0-.745-.556-.5-.96a8.956 8.956 0 001.302-4.665c0-1.194-.232-2.333-.654-3.375a.743.743 0 00-.27-.602C5.56 5.2 5.326 5.104 5.075 5.057c-.38-.072-.77.023-1.088.287A12.005 12.005 0 002 9.188c0 1.647.295 3.221.831 4.657.172.462.953.905 1.786.905h.908c.446 0 .72-.498.523-.898a8.956 8.956 0 01-.465-1.207M7.5 15l-3.114 1.04a4.501 4.501 0 00-1.423.23H1.56M7.5 15h2.25m0 0l3.114 1.04a4.501 4.501 0 001.423.23h1.374" />
          </svg>
        </button>
      </div>

      {/* Comment box for negative feedback */}
      {showComment && (
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="What could be improved?"
            className="flex-1 px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            onKeyDown={(e) => e.key === "Enter" && handleCommentSubmit()}
            autoFocus
          />
          <button
            onClick={handleCommentSubmit}
            disabled={sending}
            className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            Send
          </button>
          <button
            onClick={() => {
              setShowComment(false);
              submit(submitted || "negative");
            }}
            className="px-3 py-1.5 text-gray-500 text-sm hover:text-gray-700"
          >
            Skip
          </button>
        </div>
      )}
    </div>
  );
}
