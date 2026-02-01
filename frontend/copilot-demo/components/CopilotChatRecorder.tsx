"use client";

import { useCopilotChat } from "@copilotkit/react-core";
import { useEffect, useRef } from "react";
import { useChatMessages } from "@/contexts/ChatMessagesContext";

export function CopilotChatRecorder({ children }: { children: React.ReactNode }) {
  const { addMessage } = useChatMessages();
  // visibleMessages is deprecated but still available for compatibility
  const { visibleMessages, isLoading } = useCopilotChat();
  const lastProcessedRef = useRef<string>('');

  // DEBUG: Log loading and message state
  useEffect(() => {
    console.log('[CopilotChatRecorder] isLoading:', isLoading);
    console.log('[CopilotChatRecorder] visibleMessages count:', visibleMessages?.length || 0);
  }, [isLoading, visibleMessages]);

  useEffect(() => {
    if (visibleMessages && Array.isArray(visibleMessages)) {
      console.log('[CopilotChatRecorder] Processing messages:', visibleMessages.length);
      for (const msg of visibleMessages) {
        if (msg && typeof msg === "object") {
          const role = (msg as { role?: string }).role === "user" ? "user" : "assistant";
          const content = (msg as { content?: string }).content || "";

          console.log('[CopilotChatRecorder] Message:', { role, contentLength: content.length });

          const contentHash = `${role}:${content.substring(0, 100)}`;
          if (content && contentHash !== lastProcessedRef.current) {
            lastProcessedRef.current = contentHash;
            addMessage(role, content);
          }
        }
      }
    }
  }, [visibleMessages, addMessage]);

  return <>{children}</>;
}
