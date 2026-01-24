/**
 * useS2S - React hook for Speech-to-Speech interaction
 *
 * Manages WebSocket connection to S2S gateway, audio capture,
 * and audio playback for real-time voice interaction.
 */

import { useCallback, useRef, useState, useEffect } from 'react';
import { useAudioCapture } from './useAudioCapture';

// Message types from server
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
  /** Clear current state */
  clear: () => void;
}

// Use environment variable or construct from current hostname
// This allows the frontend to work both locally and when accessed remotely
const getDefaultServerUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    return `ws://${hostname}:8765/ws/s2s`;
  }
  return 'ws://localhost:8765/ws/s2s';
};

const DEFAULT_SERVER_URL = getDefaultServerUrl();

export function useS2S({
  serverUrl = DEFAULT_SERVER_URL,
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
  // State
  const [isConnected, setIsConnected] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isResponding, setIsResponding] = useState(false);
  const [currentTranscript, setCurrentTranscript] = useState('');
  const [currentResponse, setCurrentResponse] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<ArrayBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Audio capture hook
  const {
    isRecording,
    audioLevel,
    startRecording,
    stopRecording,
    error: audioError,
  } = useAudioCapture({
    sampleRate: 16000,
    onAudioChunk: useCallback((chunk: ArrayBuffer) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(chunk);
      }
    }, []),
    onError: useCallback((err: Error) => {
      setError(err.message);
      onError?.(err.message);
    }, [onError]),
  });

  // Initialize audio context for playback
  const getAudioContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
    }
    return audioContextRef.current;
  }, []);

  // Play PCM16 audio
  const playAudio = useCallback(
    async (pcmData: ArrayBuffer) => {
      const ctx = getAudioContext();

      // Ensure context is running (needed for user gesture requirement)
      if (ctx.state === 'suspended') {
        await ctx.resume();
      }

      // Convert PCM16 to Float32
      const int16 = new Int16Array(pcmData);
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768;
      }

      // Create audio buffer
      const buffer = ctx.createBuffer(1, float32.length, 24000);
      buffer.copyToChannel(float32, 0);

      // Play
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.start();
    },
    [getAudioContext]
  );

  // Process audio queue
  const processAudioQueue = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      return;
    }

    isPlayingRef.current = true;

    while (audioQueueRef.current.length > 0) {
      const audio = audioQueueRef.current.shift();
      if (audio) {
        await playAudio(audio);
        onTtsAudio?.(audio);
      }
    }

    isPlayingRef.current = false;
  }, [playAudio, onTtsAudio]);

  // Callbacks ref to avoid stale closures in WebSocket listeners
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

  // Update refs on render
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

  // Handle WebSocket messages
  const handleMessage = useCallback(
    (event: MessageEvent) => {
      // console.log('useS2S: handleMessage', event.data instanceof ArrayBuffer ? 'Binary' : 'Text');
      if (event.data instanceof ArrayBuffer) {
        // Binary audio data
        audioQueueRef.current.push(event.data);
        processAudioQueue();
      } else {
        // JSON message
        try {
          const msg: S2SMessage = JSON.parse(event.data);
          // console.log('useS2S: Processing message type:', msg.type);

          switch (msg.type) {
            case 'session_ready':
              console.log('S2S session ready:', msg.session_id);
              break;

            case 'asr_partial':
              setCurrentTranscript(msg.text || '');
              callbacksRef.current.onAsrPartial?.(msg.text || '');
              break;

            case 'asr_final':
              console.log('useS2S: asr_final received', msg.text);
              setCurrentTranscript(msg.text || '');
              callbacksRef.current.onAsrFinal?.(msg.text || '');
              if (msg.text) {
                setIsResponding(true);
                setCurrentResponse('');
                callbacksRef.current.onResponseStart?.();
              }
              break;

            case 'llm_token':
              setCurrentResponse((prev) => prev + (msg.token || ''));
              callbacksRef.current.onLlmToken?.(msg.token || '');
              break;

            case 'response_end':
              console.log('useS2S: response_end received');
              setIsResponding(false);
              callbacksRef.current.onResponseEnd?.();
              break;

            case 'interrupted':
              setIsResponding(false);
              audioQueueRef.current = [];
              break;

            case 'error':
              setError(msg.message || 'Unknown error');
              callbacksRef.current.onError?.(msg.message || 'Unknown error');
              break;
          }
        } catch (err) {
          console.error('Failed to parse S2S message:', err);
        }
      }
    },
    [processAudioQueue]
  );

  // Connect to server
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setError(null);

    const ws = new WebSocket(serverUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      console.log('S2S connected');
      setIsConnected(true);
      onConnectionChange?.(true);

      // Send session start
      ws.send(
        JSON.stringify({
          type: 'session_start',
          lang: language,
          audio: {
            sample_rate: 16000,
            format: 'pcm16',
            channels: 1,
          },
        })
      );
    };

    ws.onmessage = handleMessage;

    ws.onerror = (event) => {
      console.error('S2S WebSocket error:', event);
      setError('Connection error');
      onError?.('Connection error');
    };

    ws.onclose = () => {
      console.log('S2S disconnected');
      setIsConnected(false);
      setIsListening(false);
      setIsResponding(false);
      onConnectionChange?.(false);
      wsRef.current = null;
    };

    wsRef.current = ws;
  }, [serverUrl, language, handleMessage, onConnectionChange, onError]);

  // Disconnect
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    stopRecording();

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
    setIsListening(false);
    setIsResponding(false);
  }, [stopRecording]);

  // Start listening
  const startListeningFn = useCallback(() => {
    if (!isConnected) {
      connect();
      // Wait for connection then start
      const checkConnection = setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          clearInterval(checkConnection);
          startRecording();
          setIsListening(true);
          setCurrentTranscript('');
        }
      }, 100);

      // Timeout after 5 seconds
      setTimeout(() => clearInterval(checkConnection), 5000);
    } else {
      startRecording();
      setIsListening(true);
      setCurrentTranscript('');
    }
  }, [isConnected, connect, startRecording]);

  // Stop listening
  const stopListeningFn = useCallback(() => {
    stopRecording();
    setIsListening(false);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'audio_end' }));
    }
  }, [stopRecording]);

  // Interrupt response
  const interrupt = useCallback(() => {
    audioQueueRef.current = [];
    setIsResponding(false);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'interrupt' }));
    }
  }, []);

  // Send text directly
  const sendText = useCallback(
    (text: string) => {
      if (!text.trim()) return;

      if (!isConnected) {
        connect();
        // Queue the text to send after connection
        const checkConnection = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            clearInterval(checkConnection);
            wsRef.current.send(
              JSON.stringify({
                type: 'text_input',
                text: text.trim(),
              })
            );
            setIsResponding(true);
            setCurrentResponse('');
            onResponseStart?.();
          }
        }, 100);

        setTimeout(() => clearInterval(checkConnection), 5000);
      } else if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'text_input',
            text: text.trim(),
          })
        );
        setIsResponding(true);
        setCurrentResponse('');
        onResponseStart?.();
      }
    },
    [isConnected, connect, onResponseStart]
  );

  // Clear state
  const clear = useCallback(() => {
    setCurrentTranscript('');
    setCurrentResponse('');
    setError(null);
  }, []);

  // Auto-connect
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync audio error
  useEffect(() => {
    if (audioError) {
      setError(audioError);
    }
  }, [audioError]);

  return {
    // State
    isConnected,
    isListening: isListening && isRecording,
    isResponding,
    currentTranscript,
    currentResponse,
    audioLevel,
    error,
    // Controls
    connect,
    disconnect,
    startListening: startListeningFn,
    stopListening: stopListeningFn,
    interrupt,
    sendText,
    clear,
  };
}
