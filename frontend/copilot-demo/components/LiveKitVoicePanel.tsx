'use client';

/**
 * LiveKitVoicePanel - Full-featured LiveKit voice interaction panel
 * 
 * Provides WebRTC-based voice interaction with BestBox voice agent
 * Features:
 * - Real-time speech-to-speech with ~200-800ms latency
 * - Semantic turn detection
 * - Visual feedback for speaking/listening states
 * - Conversation history display
 * - Connection status indicators
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { useLiveKitRoom } from '@/hooks/useLiveKitRoom';
import { AudioVisualizer } from '@livekit/components-react';
import { Track } from 'livekit-client';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface LiveKitVoicePanelProps {
  /** LiveKit server URL */
  serverUrl: string;
  /** Room API token */
  token: string;
  /** Panel title */
  title?: string;
  /** Additional CSS classes */
  className?: string;
  /** Auto-connect on mount */
  autoConnect?: boolean;
}

export function LiveKitVoicePanel({
  serverUrl,
  token,
  title = 'Voice Assistant',
  className = '',
  autoConnect = false,
}: LiveKitVoicePanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAudioReady, setIsAudioReady] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentUserMessageRef = useRef<string>('');
  const currentAgentMessageRef = useRef<string>('');

  // LiveKit room state
  const {
    room,
    isConnected,
    isConnecting,
    agentIsSpeaking,
    transcript,
    agentResponse,
    error,
    connect,
    disconnect,
    setMicEnabled,
    micEnabled,
  } = useLiveKitRoom({
    url: serverUrl,
    token,
    autoConnect,
  });

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle transcript updates
  useEffect(() => {
    if (transcript && transcript !== currentUserMessageRef.current) {
      currentUserMessageRef.current = transcript;

      // Add or update user message
      setMessages(prev => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && lastMessage.role === 'user' && lastMessage.content !== transcript) {
          // Update existing user message
          return [
            ...prev.slice(0, -1),
            { ...lastMessage, content: transcript }
          ];
        } else if (!lastMessage || lastMessage.role !== 'user') {
          // Add new user message
          return [
            ...prev,
            {
              id: `user-${Date.now()}`,
              role: 'user',
              content: transcript,
              timestamp: new Date(),
            }
          ];
        }
        return prev;
      });
    }
  }, [transcript]);

  // Handle agent response updates
  useEffect(() => {
    if (agentResponse && agentResponse !== currentAgentMessageRef.current) {
      currentAgentMessageRef.current = agentResponse;

      // Add or update agent message
      setMessages(prev => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && lastMessage.role === 'assistant' && lastMessage.content !== agentResponse) {
          // Update existing agent message
          return [
            ...prev.slice(0, -1),
            { ...lastMessage, content: agentResponse }
          ];
        } else if (!lastMessage || lastMessage.role !== 'assistant') {
          // Add new agent message
          return [
            ...prev,
            {
              id: `agent-${Date.now()}`,
              role: 'assistant',
              content: agentResponse,
              timestamp: new Date(),
            }
          ];
        }
        return prev;
      });
    }
  }, [agentResponse]);

  // Toggle connection
  const handleToggleConnection = useCallback(async () => {
    if (isConnected) {
      disconnect();
      setIsAudioReady(false);
    } else {
      // This is a user gesture, safe to connect and start audio
      setIsAudioReady(true);
      await connect();
    }
  }, [isConnected, connect, disconnect]);

  // Toggle microphone
  const handleToggleMic = useCallback(async () => {
    await setMicEnabled(!micEnabled);
  }, [micEnabled, setMicEnabled]);

  // Clear conversation
  const handleClearConversation = useCallback(() => {
    setMessages([]);
    currentUserMessageRef.current = '';
    currentAgentMessageRef.current = '';
  }, []);

  return (
    <div className={`flex flex-col h-full bg-white rounded-xl shadow-lg ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">{title}</h2>
          <p className="text-sm text-gray-500">
            {isConnecting ? 'Connecting...' :
              isConnected ? '🟢 Connected' :
                '🔴 Disconnected'}
          </p>
        </div>

        <div className="flex gap-2">
          {/* Connection toggle */}
          <button
            onClick={handleToggleConnection}
            disabled={isConnecting}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${isConnected
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-blue-500 hover:bg-blue-600 text-white'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {isConnecting ? 'Connecting...' : isConnected ? 'Disconnect' : 'Connect'}
          </button>

          {/* Clear button */}
          {messages.length > 0 && (
            <button
              onClick={handleClearConversation}
              className="px-3 py-2 rounded-lg bg-gray-200 hover:bg-gray-300 text-gray-700 transition-colors"
              title="Clear conversation"
            >
              🗑️
            </button>
          )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">❌ {error}</p>
        </div>
      )}

      {/* Audio ready notification */}
      {isAudioReady && isConnected && (
        <div className="mx-4 mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-sm text-green-700">✅ Audio system ready! Start speaking to interact with BestBox.</p>
        </div>
      )}

      {/* Connection guide */}
      {!isConnected && !isConnecting && !error && (
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="max-w-md text-center">
            <div className="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <span className="text-5xl">🎤</span>
            </div>
            <h3 className="text-2xl font-bold text-gray-800 mb-3">Ready to Start</h3>
            <p className="text-gray-600 mb-2">
              Click the button below to connect and start your voice conversation with BestBox AI
            </p>
            <p className="text-xs text-green-600 mb-4">
              ✅ Audio fix v1.1 - Browser autoplay handled
            </p>
            <button
              onClick={handleToggleConnection}
              className="px-8 py-4 bg-blue-500 hover:bg-blue-600 text-white text-lg font-semibold rounded-xl transition-colors shadow-lg hover:shadow-xl"
            >
              🎙️ Start Voice Session
            </button>
            <div className="mt-8 p-4 bg-blue-50 border border-blue-200 rounded-lg text-left">
              <h4 className="font-semibold text-blue-900 mb-2">💡 How to Use</h4>
              <ol className="text-sm text-blue-800 space-y-1">
                <li>1. Click "Start Voice Session" above</li>
                <li>2. Allow microphone access when prompted</li>
                <li>3. Start speaking - the agent will respond in real-time</li>
                <li>4. Semantic turn detection (no need to press buttons)</li>
              </ol>
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && isConnected && (
          <div className="text-center py-8">
            <p className="text-gray-500 mb-2">🎙️ Start speaking to interact with BestBox</p>
            <p className="text-sm text-gray-400">
              Try: "What are the top vendors?" or "Show me customer ABC Corp"
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg p-3 ${msg.role === 'user'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-800'
                }`}
            >
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              <p
                className={`text-xs mt-1 ${msg.role === 'user' ? 'text-blue-100' : 'text-gray-500'
                  }`}
              >
                {msg.timestamp.toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Status bar */}
      {isConnected && (
        <div className="border-t p-4 bg-gray-50">
          <div className="flex items-center justify-between">
            {/* Mic status */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleToggleMic}
                className={`p-3 rounded-full transition-colors ${micEnabled
                  ? 'bg-green-500 hover:bg-green-600 text-white'
                  : 'bg-red-500 hover:bg-red-600 text-white'
                  }`}
                title={micEnabled ? 'Mute microphone' : 'Unmute microphone'}
              >
                {micEnabled ? '🎤' : '🔇'}
              </button>
              <span className="text-sm text-gray-600">
                {micEnabled ? 'Microphone Active' : 'Microphone Muted'}
              </span>
            </div>

            {/* Speaking indicator */}
            <div className="flex items-center gap-2">
              {agentIsSpeaking && (
                <>
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  <span className="text-sm text-gray-600">Agent Speaking</span>
                </>
              )}
            </div>
          </div>

          {/* Audio visualizer (if available) */}
          {room && micEnabled && room.localParticipant.audioTrackPublications.values().next().value && (
            <div className="mt-3">
              <AudioVisualizer
                trackRef={{
                  participant: room.localParticipant,
                  source: Track.Source.Microphone,
                  publication: room.localParticipant.audioTrackPublications.values().next().value!,
                }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
