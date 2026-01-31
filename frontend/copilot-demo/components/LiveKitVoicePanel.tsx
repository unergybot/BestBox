'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useLiveKitRoom } from '@/hooks/useLiveKitRoom';
import { AudioVisualizer } from '@livekit/components-react';
import { Track } from 'livekit-client';
import { useChatMessages } from '@/contexts/ChatMessagesContext';

interface LiveKitVoicePanelProps {
  serverUrl: string;
  token: string;
  title?: string;
  className?: string;
  autoConnect?: boolean;
}

export function LiveKitVoicePanel({
  serverUrl,
  token,
  title = 'Voice Assistant',
  className = '',
  autoConnect = false,
}: LiveKitVoicePanelProps) {
  const [isAudioReady, setIsAudioReady] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentUserMessageRef = useRef<string>('');
  const currentAgentMessageRef = useRef<string>('');
  const { addMessage } = useChatMessages();

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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript, agentResponse]);

  useEffect(() => {
    if (transcript && transcript !== currentUserMessageRef.current) {
      currentUserMessageRef.current = transcript;
      console.log("=== LiveKitVoicePanel ===");
      console.log("Adding user transcript to context:", transcript?.substring(0, 50));
      addMessage("user", transcript);
    }
  }, [transcript, addMessage]);

  useEffect(() => {
    if (agentResponse && agentResponse !== currentAgentMessageRef.current) {
      currentAgentMessageRef.current = agentResponse;
      console.log("=== LiveKitVoicePanel ===");
      console.log("Adding agent response to context:", agentResponse?.substring(0, 50));
      addMessage("assistant", agentResponse);
    }
  }, [agentResponse, addMessage]);

  const handleToggleConnection = useCallback(async () => {
    if (isConnected) {
      disconnect();
      setIsAudioReady(false);
    } else {
      setIsAudioReady(true);
      await connect();
    }
  }, [isConnected, connect, disconnect]);

  const handleToggleMic = useCallback(async () => {
    await setMicEnabled(!micEnabled);
  }, [micEnabled, setMicEnabled]);

  return (
    <div className={`flex flex-col h-full bg-white rounded-xl shadow-lg ${className}`}>
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">{title}</h2>
          <p className="text-sm text-gray-500">
            {isConnecting ? 'Connecting...' :
              isConnected ? '🟢 Connected' :
                '🔴 Disconnected'}
          </p>
        </div>

        <button
          onClick={handleToggleConnection}
          disabled={isConnecting}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${isConnected
            ? 'bg-red-500 hover:bg-red-600 text-white'
            : 'bg-blue-500 hover:bg-blue-600 text-white'
            } disabled:opacity-50`}
        >
          {isConnecting ? 'Connecting...' : isConnected ? 'Disconnect' : 'Connect'}
        </button>
      </div>

      {error && (
        <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">❌ {error}</p>
        </div>
      )}

      {!isConnected && !isConnecting && !error && (
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="max-w-md text-center">
            <div className="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <span className="text-5xl">🎤</span>
            </div>
            <h3 className="text-2xl font-bold text-gray-800 mb-3">Ready to Start</h3>
            <button
              onClick={handleToggleConnection}
              className="px-8 py-4 bg-blue-500 hover:bg-blue-600 text-white text-lg font-semibold rounded-xl transition-colors shadow-lg"
            >
              🎙️ Start Voice Session
            </button>
          </div>
        </div>
      )}

      {isConnected && (
        <div className="flex-1 overflow-y-auto p-4">
          <LiveKitMessagesContainer />
          <div ref={messagesEndRef} />
        </div>
      )}

      {isConnected && (
        <div className="border-t p-4 bg-gray-50">
          <div className="flex items-center justify-between">
            <button
              onClick={handleToggleMic}
              className={`p-3 rounded-full transition-colors ${micEnabled
                ? 'bg-green-500 hover:bg-green-600 text-white'
                : 'bg-red-500 hover:bg-red-600 text-white'
                }`}
            >
              {micEnabled ? '🎤' : '🔇'}
            </button>
            <div className="flex items-center gap-2">
              {agentIsSpeaking && (
                <>
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  <span className="text-sm text-gray-600">Agent Speaking</span>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useChatMessages as useLiveKitMessages } from '@/contexts/ChatMessagesContext';

function LiveKitMessagesContainer() {
  const { messages } = useLiveKitMessages();

  if (messages.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500">🎙️ Start speaking to interact with BestBox</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {messages.map((msg) => (
        <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`max-w-[80%] rounded-lg p-3 ${msg.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-800'}`}>
            <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
