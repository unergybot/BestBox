'use client';

/**
 * VoicePanel - Full-featured voice interaction panel
 *
 * Includes voice button, conversation history, and text input fallback.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { VoiceButton } from './VoiceButton';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface VoicePanelProps {
  /** S2S server URL */
  serverUrl?: string;
  /** Recognition language */
  language?: string;
  /** Panel title */
  title?: string;
  /** Show text input */
  showTextInput?: boolean;
  /** Additional CSS classes */
  className?: string;
}

export function VoicePanel({
  serverUrl,
  language = 'zh',
  title = '语音助手',
  showTextInput = true,
  className = '',
}: VoicePanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [textInput, setTextInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle transcript from voice
  const handleTranscript = useCallback((text: string) => {
    if (!text.trim()) return;

    const message: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, message]);
  }, []);

  // Handle response from voice
  const handleResponse = useCallback((text: string) => {
    if (!text.trim()) return;

    const message: Message = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, message]);
  }, []);

  // Handle text input submit
  const handleTextSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!textInput.trim()) return;

      // Add user message
      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: textInput,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setTextInput('');

      // TODO: Send to S2S via text_input
    },
    [textInput]
  );

  // Clear conversation
  const handleClear = useCallback(() => {
    setMessages([]);
  }, []);

  return (
    <div
      className={`flex flex-col bg-white dark:bg-gray-900 rounded-xl shadow-lg overflow-hidden ${className}`}
      style={{ height: '600px', width: '400px' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white">
        <h2 className="font-semibold">{title}</h2>
        <button
          onClick={handleClear}
          className="text-sm opacity-80 hover:opacity-100 transition-opacity"
        >
          清除
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            <p className="text-sm">点击下方麦克风开始对话</p>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  message.role === 'user'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100'
                }`}
              >
                <p className="text-sm">{message.content}</p>
                <p
                  className={`text-xs mt-1 ${
                    message.role === 'user'
                      ? 'text-blue-200'
                      : 'text-gray-400'
                  }`}
                >
                  {message.timestamp.toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Voice button */}
      <div className="flex justify-center py-4 border-t border-gray-200 dark:border-gray-700">
        <VoiceButton
          serverUrl={serverUrl}
          language={language}
          onTranscript={handleTranscript}
          onResponse={handleResponse}
          showText={false}
          size="lg"
        />
      </div>

      {/* Text input fallback */}
      {showTextInput && (
        <form
          onSubmit={handleTextSubmit}
          className="flex gap-2 p-3 border-t border-gray-200 dark:border-gray-700"
        >
          <input
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="或者输入文字..."
            className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-white"
          />
          <button
            type="submit"
            disabled={!textInput.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-500 rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            发送
          </button>
        </form>
      )}
    </div>
  );
}

export default VoicePanel;
