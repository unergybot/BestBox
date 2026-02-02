/**
 * useS2S - React hook for Speech-to-Speech interaction
 *
 * This hook now uses the S2SClient singleton to ensure the WebSocket connection
 * persists across component lifecycle events. The VoiceInput component can be
 * unmounted and remounted by CopilotSidebar without losing the connection.
 *
 * Key difference from previous implementation:
 * - On unmount: Only removes event listeners, does NOT disconnect WebSocket
 * - Connection is managed by the singleton, which auto-reconnects if needed
 */

import { useCallback, useState, useEffect, useRef } from 'react';
import { S2SClient, getS2SClient } from '@/lib/S2SClient';

export interface S2SMessage {
  type:
  | 'session_ready'
  | 'asr_partial'
  | 'asr_final'
  | 'llm_token'
  | 'response_end'
  | 'interrupted'
  | 'error';
  text?: string;
  token?: string;
  message?: string;
  session_id?: string;
}

export interface UseS2SOptions {
  /** WebSocket server URL */
  serverUrl?: string;
  /** Recognition language (zh, en, etc.) */
  language?: string;
  /** Auto-connect on mount */
  autoConnect?: boolean;

  // Callbacks
  onAsrPartial?: (text: string) => void;
  onAsrFinal?: (text: string) => void;
  onLlmToken?: (token: string) => void;
  onTtsAudio?: (audio: ArrayBuffer) => void;
  onResponseStart?: () => void;
  onResponseEnd?: () => void;
  onError?: (error: string) => void;
  onConnectionChange?: (connected: boolean) => void;
}

export interface S2SState {
  /** WebSocket connected */
  isConnected: boolean;
  /** Currently listening to microphone */
  isListening: boolean;
  /** Currently receiving/playing response */
  isResponding: boolean;
  /** Current partial transcript */
  currentTranscript: string;
  /** Current response text */
  currentResponse: string;
  /** Audio input level (0-1) */
  audioLevel: number;
  /** Error message */
  error: string | null;
}

export interface S2SControls {
  /** Connect to server */
  connect: () => void;
  /** Disconnect from server */
  disconnect: () => void;
  /** Start listening (mic on) */
  startListening: () => void;
  /** Stop listening (mic off, triggers ASR finalize) */
  stopListening: () => void;
  /** Interrupt current response */
  interrupt: () => void;
  /** Send text directly (skip speech) */
  sendText: (text: string) => void;
  /** Request TTS for text */
  speak: (text: string, flush?: boolean) => void;
  /** Clear current state */
  clear: () => void;
}

// Get default server URL (same as singleton default)
const getDefaultServerUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    return `ws://${hostname}:8765/ws/s2s`;
  }
  return 'ws://localhost:8765/ws/s2s';
};

export function useS2S({
  serverUrl,
  language = 'zh',
  autoConnect = false,
  onAsrPartial,
  onAsrFinal,
  onLlmToken,
  onTtsAudio,
  onResponseStart,
  onResponseEnd,
  onError,
  onConnectionChange,
}: UseS2SOptions = {}): S2SState & S2SControls {
  // State synced from singleton
  const [isConnected, setIsConnected] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isResponding, setIsResponding] = useState(false);
  const [currentTranscript, setCurrentTranscript] = useState('');
  const [currentResponse, setCurrentResponse] = useState('');
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Keep callbacks in ref to avoid stale closures
  const callbacksRef = useRef({
    onAsrPartial,
    onAsrFinal,
    onLlmToken,
    onTtsAudio,
    onResponseStart,
    onResponseEnd,
    onError,
    onConnectionChange,
  });

  // Update refs on each render
  useEffect(() => {
    callbacksRef.current = {
      onAsrPartial,
      onAsrFinal,
      onLlmToken,
      onTtsAudio,
      onResponseStart,
      onResponseEnd,
      onError,
      onConnectionChange,
    };
  }, [onAsrPartial, onAsrFinal, onLlmToken, onTtsAudio, onResponseStart, onResponseEnd, onError, onConnectionChange]);

  // Get singleton client
  const clientRef = useRef<S2SClient | null>(null);

  useEffect(() => {
    const client = getS2SClient();
    clientRef.current = client;

    // Configure client
    if (serverUrl) {
      client.setServerUrl(serverUrl);
    }
    client.setLanguage(language);

    // Sync initial state
    const state = client.getState();
    setIsConnected(state.isConnected);
    setIsListening(state.isListening);
    setIsResponding(state.isResponding);
    setCurrentTranscript(state.currentTranscript);
    setCurrentResponse(state.currentResponse);
    setAudioLevel(state.audioLevel);
    setError(state.error);

    // Event listeners
    const onConnecting = () => {
      console.log('useS2S: Connecting...');
    };

    const onConnected = () => {
      console.log('useS2S: Connected');
      setIsConnected(true);
      callbacksRef.current.onConnectionChange?.(true);
    };

    const onDisconnected = () => {
      console.log('useS2S: Disconnected');
      setIsConnected(false);
      setIsListening(false);
      callbacksRef.current.onConnectionChange?.(false);
    };

    const onSessionReady = (data: { sessionId: string }) => {
      console.log('useS2S: Session ready:', data.sessionId);
    };

    const onAsrPartialEvent = (data: { text: string }) => {
      setCurrentTranscript(data.text);
      callbacksRef.current.onAsrPartial?.(data.text);
    };

    const onAsrFinalEvent = (data: { text: string }) => {
      console.log('useS2S: ASR final:', data.text);
      setCurrentTranscript(data.text);
      callbacksRef.current.onAsrFinal?.(data.text);
    };

    const onLlmTokenEvent = (data: { token: string }) => {
      setCurrentResponse(prev => prev + data.token);
      callbacksRef.current.onLlmToken?.(data.token);
    };

    const onResponseStartEvent = () => {
      setIsResponding(true);
      setCurrentResponse('');
      callbacksRef.current.onResponseStart?.();
    };

    const onResponseEndEvent = () => {
      console.log('useS2S: Response end');
      setIsResponding(false);
      callbacksRef.current.onResponseEnd?.();
    };

    const onTtsAudioEvent = (data: { audio: ArrayBuffer }) => {
      callbacksRef.current.onTtsAudio?.(data.audio);
    };

    const onInterruptedEvent = () => {
      setIsResponding(false);
    };

    const onErrorEvent = (data: { message: string }) => {
      setError(data.message);
      callbacksRef.current.onError?.(data.message);
    };

    const onAudioLevelEvent = (data: { level: number }) => {
      setAudioLevel(data.level);
    };

    // Subscribe to events
    client.on('connecting', onConnecting);
    client.on('connected', onConnected);
    client.on('disconnected', onDisconnected);
    client.on('session_ready', onSessionReady);
    client.on('asr_partial', onAsrPartialEvent);
    client.on('asr_final', onAsrFinalEvent);
    client.on('llm_token', onLlmTokenEvent);
    client.on('response_start', onResponseStartEvent);
    client.on('response_end', onResponseEndEvent);
    client.on('tts_audio', onTtsAudioEvent);
    client.on('interrupted', onInterruptedEvent);
    client.on('error', onErrorEvent);
    client.on('audio_level', onAudioLevelEvent);

    // Auto-connect if requested
    if (autoConnect && !state.isConnected) {
      client.connect();
    }

    // Cleanup: Remove listeners but DO NOT disconnect
    // This is critical for the singleton pattern - connection survives unmount
    return () => {
      client.off('connecting', onConnecting);
      client.off('connected', onConnected);
      client.off('disconnected', onDisconnected);
      client.off('session_ready', onSessionReady);
      client.off('asr_partial', onAsrPartialEvent);
      client.off('asr_final', onAsrFinalEvent);
      client.off('llm_token', onLlmTokenEvent);
      client.off('response_start', onResponseStartEvent);
      client.off('response_end', onResponseEndEvent);
      client.off('tts_audio', onTtsAudioEvent);
      client.off('interrupted', onInterruptedEvent);
      client.off('error', onErrorEvent);
      client.off('audio_level', onAudioLevelEvent);
    };
  }, [serverUrl, language, autoConnect]);

  // Controls
  const connect = useCallback(() => {
    clientRef.current?.connect();
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
  }, []);

  const startListening = useCallback(async () => {
    try {
      await clientRef.current?.startListening();
      setIsListening(true);
      setCurrentTranscript('');
    } catch (e) {
      console.error('useS2S: Failed to start listening', e);
    }
  }, []);

  const stopListening = useCallback(() => {
    clientRef.current?.stopListening();
    setIsListening(false);
  }, []);

  const interrupt = useCallback(() => {
    clientRef.current?.interrupt();
    setIsResponding(false);
  }, []);

  const sendText = useCallback((text: string) => {
    clientRef.current?.sendText(text);
  }, []);

  const speak = useCallback((text: string, flush: boolean = true) => {
    clientRef.current?.speak(text, flush);
  }, []);

  const clear = useCallback(() => {
    clientRef.current?.clear();
    setCurrentTranscript('');
    setCurrentResponse('');
    setError(null);
  }, []);

  return {
    // State
    isConnected,
    isListening,
    isResponding,
    currentTranscript,
    currentResponse,
    audioLevel,
    error,
    // Controls
    connect,
    disconnect,
    startListening,
    stopListening,
    interrupt,
    sendText,
    speak,
    clear,
  };
}
