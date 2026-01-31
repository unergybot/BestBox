"use client";

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface ChatMessagesContextType {
  messages: ChatMessage[];
  addMessage: (role: "user" | "assistant", content: string) => void;
  updateLastAssistantMessage: (content: string) => void;
  clearMessages: () => void;
}

const ChatMessagesContext = createContext<ChatMessagesContextType | null>(null);

export function ChatMessagesProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const addMessage = useCallback((role: "user" | "assistant", content: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `${role}-${Date.now()}`,
        role,
        content,
        timestamp: new Date(),
      },
    ]);
  }, []);

  const updateLastAssistantMessage = useCallback((content: string) => {
    setMessages((prev) => {
      const lastMsg = prev[prev.length - 1];
      if (lastMsg && lastMsg.role === "assistant") {
        return prev.map((msg) =>
          msg.id === lastMsg.id ? { ...msg, content } : msg
        );
      }
      return prev;
    });
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return (
    <ChatMessagesContext.Provider value={{ messages, addMessage, updateLastAssistantMessage, clearMessages }}>
      {children}
    </ChatMessagesContext.Provider>
  );
}

export function useChatMessages() {
  const context = useContext(ChatMessagesContext);
  if (!context) {
    throw new Error('useChatMessages must be used within a ChatMessagesProvider');
  }
  return context;
}

export function useChatMessagesForTroubleshooting() {
  const context = useContext(ChatMessagesContext);
  if (!context) {
    return [];
  }
  return context.messages;
}
