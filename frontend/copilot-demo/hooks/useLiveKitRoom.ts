/**
 * useLiveKitRoom - React hook for managing LiveKit voice agent rooms
 * 
 * Provides complete room management for interacting with BestBox voice agent
 */

import { useEffect, useState, useCallback } from 'react';
import { Room, RoomEvent, Track, RemoteTrackPublication, RemoteParticipant } from 'livekit-client';

export interface LiveKitRoomConfig {
  /** LiveKit server URL */
  url: string;
  /** Room API token */
  token: string;
  /** Auto-connect on mount */
  autoConnect?: boolean;
}

export interface LiveKitRoomState {
  /** Room instance */
  room: Room | null;
  /** Connection state */
  isConnected: boolean;
  /** Is connecting */
  isConnecting: boolean;
  /** Agent is speaking */
  agentIsSpeaking: boolean;
  /** Interim/partial transcript (real-time while speaking) */
  interimTranscript: string;
  /** Final transcript text */
  transcript: string;
  /** Agent response text */
  agentResponse: string;
  /** Connection error */
  error: string | null;
}

export interface UseLiveKitRoomReturn extends LiveKitRoomState {
  /** Connect to room */
  connect: () => Promise<void>;
  /** Disconnect from room */
  disconnect: () => void;
  /** Enable/disable microphone */
  setMicEnabled: (enabled: boolean) => Promise<void>;
  /** Current mic state */
  micEnabled: boolean;
}

/**
 * Get LiveKit token from backend
 */
async function getLiveKitToken(roomName: string): Promise<string> {
  const response = await fetch('/api/livekit/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ roomName }),
  });

  if (!response.ok) {
    throw new Error(`Failed to get token: ${response.statusText}`);
  }

  const data = await response.json();
  return data.token;
}

export function useLiveKitRoom(config: LiveKitRoomConfig): UseLiveKitRoomReturn {
  const [room, setRoom] = useState<Room | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [agentIsSpeaking, setAgentIsSpeaking] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState('');
  const [transcript, setTranscript] = useState('');
  const [agentResponse, setAgentResponse] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [micEnabled, setMicEnabledState] = useState(false);

  // Create room instance
  useEffect(() => {
    const newRoom = new Room({
      // Configure for voice agent
      adaptiveStream: true,
      dynacast: true,
      videoCaptureDefaults: {
        resolution: { width: 0, height: 0 }, // No video
      },
    });

    setRoom(newRoom);

    return () => {
      newRoom.disconnect();
    };
  }, []);

  // Set up room event listeners
  useEffect(() => {
    if (!room) return;

    const handleConnected = () => {
      console.log('[LiveKit] Connected to room');
      setIsConnected(true);
      setIsConnecting(false);
      setError(null);
    };

    const handleDisconnected = () => {
      console.log('[LiveKit] Disconnected from room');
      setIsConnected(false);
      setIsConnecting(false);
      setAgentIsSpeaking(false);
      setInterimTranscript('');  // Reset interim transcript
      setTranscript('');  // Reset transcript state
      setAgentResponse('');  // Reset agent response state
    };

    const handleReconnecting = () => {
      console.log('[LiveKit] Reconnecting...');
      setIsConnecting(true);
    };

    const handleReconnected = () => {
      console.log('[LiveKit] Reconnected');
      setIsConnecting(false);
    };

    // Handle agent audio tracks
    const handleTrackSubscribed = (
      track: Track,
      publication: RemoteTrackPublication,
      participant: RemoteParticipant
    ) => {
      if (track.kind === Track.Kind.Audio) {
        console.log('[LiveKit] Agent audio track subscribed');

        // Attach audio element with proper configuration
        const audioElement = track.attach() as HTMLAudioElement;
        audioElement.autoplay = true;
        // playsInline is for video, not needed for audio
        // (audioElement as any).playsInline = true;
        audioElement.controls = false;

        // Add to DOM to ensure it's managed properly
        audioElement.style.display = 'none';
        document.body.appendChild(audioElement);

        // Store reference for cleanup
        (track as any)._audioElement = audioElement;

        // Attempt to play audio with better error handling
        const playAudio = async () => {
          try {
            // Ensure audio context is resumed (in case it was suspended)
            const audioCtx = (room as any).audioContext;
            if (audioCtx?.state === 'suspended') {
              await audioCtx.resume();
              console.log('[LiveKit] Audio context resumed');
            }

            await audioElement.play();
            console.log('[LiveKit] Audio playback started successfully');
          } catch (e: any) {
            if (e.name === 'NotAllowedError') {
              console.warn('[LiveKit] Audio playback blocked by browser. Adding interaction listener...');

              // Create a more persistent audio resume handler
              const resumeAudio = async (event: Event) => {
                try {
                  // Resume audio context if needed
                  const audioCtx = (room as any).audioContext;
                  if (audioCtx?.state === 'suspended') {
                    await audioCtx.resume();
                  }

                  await audioElement.play();
                  console.log('[LiveKit] Audio playback resumed after user interaction');

                  // Remove all listeners after successful resume
                  document.removeEventListener('click', resumeAudio);
                  document.removeEventListener('touchstart', resumeAudio);
                  document.removeEventListener('keydown', resumeAudio);
                } catch (retryError) {
                  console.error('[LiveKit] Failed to resume audio:', retryError);
                }
              };

              // Add multiple event listeners for better coverage
              document.addEventListener('click', resumeAudio, { once: true });
              document.addEventListener('touchstart', resumeAudio, { once: true });
              document.addEventListener('keydown', resumeAudio, { once: true });

              // (track as any).on('data', onTrackData);

            } else {
              console.error('[LiveKit] Failed to play audio:', e);
            }
          }
        };

        // Delay playback slightly to ensure track is fully ready
        setTimeout(playAudio, 100);
      }
    };

    const handleTrackUnsubscribed = (
      track: Track,
      publication: RemoteTrackPublication,
      participant: RemoteParticipant
    ) => {
      if (track.kind === Track.Kind.Audio) {
        console.log('[LiveKit] Agent audio track unsubscribed');

        // Clean up audio element properly
        const audioElement = (track as any)._audioElement;
        if (audioElement && audioElement.parentNode) {
          audioElement.pause();
          audioElement.parentNode.removeChild(audioElement);
        }

        track.detach();
        setAgentIsSpeaking(false);
      }
    };

    // Handle audio activity
    const handleActiveSpeakers = (speakers: any[]) => {
      const agentSpeaking = speakers.some(s => !s.isLocal);
      setAgentIsSpeaking(agentSpeaking);
    };

    // Handle data messages (transcripts, agent responses)
    const handleDataReceived = (
      payload: Uint8Array,
      participant?: RemoteParticipant,
      kind?: any
    ) => {
      const decoder = new TextDecoder();
      const text = decoder.decode(payload);

      try {
        const data = JSON.parse(text);
        console.log('[LiveKit] Data received:', data.type, data);

        // Handle different message types
        if (data.type === 'user_transcript_partial') {
          // Interim/partial transcript while user is speaking
          console.log('[LiveKit] Interim transcript:', data.text);
          setInterimTranscript(data.text);
        } else if (data.type === 'transcript' || data.type === 'user_transcript') {
          // Final transcript when user stops speaking
          console.log('[LiveKit] User transcript:', data.text);
          setTranscript(data.text);
          setInterimTranscript('');  // Clear interim when final arrives
        } else if (data.type === 'agent_response') {
          console.log('[LiveKit] Agent response:', data.text);
          setAgentResponse(prev => prev + data.text);
        } else if (data.type === 'greeting') {
          // Initial greeting - treat as agent response for display
          console.log('[LiveKit] Greeting received:', data.text);
          setAgentResponse(data.text);
        } else if (data.type === 'agent_response_complete') {
          // Response finished - reset for next interaction
          console.log('[LiveKit] Agent response complete');
          // Brief delay to ensure final callback fires, then reset
          setTimeout(() => {
            setAgentResponse('');
          }, 100);
        } else if (data.type === 'greet_sent') {
          console.log('[LiveKit] Agent sent initial greeting');
        } else if (data.type === 'agent_ready') {
          console.log('[LiveKit] Agent is ready');
        } else {
          console.log('[LiveKit] Unknown message type:', data.type, data);
        }
      } catch (e) {
        console.warn('[LiveKit] Failed to parse data message:', e, 'Raw text:', text);
      }
    };

    // Register event listeners
    room.on(RoomEvent.Connected, handleConnected);
    room.on(RoomEvent.Disconnected, handleDisconnected);
    room.on(RoomEvent.Reconnecting, handleReconnecting);
    room.on(RoomEvent.Reconnected, handleReconnected);
    room.on(RoomEvent.TrackSubscribed, handleTrackSubscribed);
    room.on(RoomEvent.TrackUnsubscribed, handleTrackUnsubscribed);
    room.on(RoomEvent.DataReceived, handleDataReceived);
    room.on(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakers);

    return () => {
      room.off(RoomEvent.Connected, handleConnected);
      room.off(RoomEvent.Disconnected, handleDisconnected);
      room.off(RoomEvent.Reconnecting, handleReconnecting);
      room.off(RoomEvent.Reconnected, handleReconnected);
      room.off(RoomEvent.TrackSubscribed, handleTrackSubscribed);
      room.off(RoomEvent.TrackUnsubscribed, handleTrackUnsubscribed);
      room.off(RoomEvent.DataReceived, handleDataReceived);
      room.off(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakers);
    };
  }, [room]);

  // Connect to room
  const connect = useCallback(async () => {
    if (!room || isConnected || isConnecting) return;

    try {
      setIsConnecting(true);
      setError(null);

      console.log('[LiveKit] Starting connection process...');

      // Request microphone permission explicitly first
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        console.log('[LiveKit] Microphone permission granted');
        stream.getTracks().forEach(track => track.stop()); // Clean up test stream
      } catch (permErr: any) {
        if (permErr.name === 'NotAllowedError') {
          throw new Error('Microphone permission denied. Please allow access in browser settings and refresh the page.');
        }
        throw permErr;
      }

      // CRITICAL: Start audio context before connecting (requires user gesture)
      // This must be called in response to a user action (click, tap, etc.)
      try {
        await room.startAudio();
        console.log('[LiveKit] Audio context started successfully');
      } catch (audioError) {
        console.warn('[LiveKit] Failed to start audio context:', audioError);
        // Continue anyway - audio might work later
      }

      console.log('[LiveKit] Connecting to:', config.url);
      await room.connect(config.url, config.token);

      // Enable microphone by default
      await room.localParticipant.setMicrophoneEnabled(true);
      setMicEnabledState(true);

      console.log('[LiveKit] Connection successful');
    } catch (err) {
      console.error('[LiveKit] Connection failed:', err);
      setError(err instanceof Error ? err.message : 'Connection failed');
      setIsConnecting(false);
    }
  }, [room, isConnected, isConnecting, config.url, config.token]);

  // Disconnect from room
  const disconnect = useCallback(() => {
    if (room && isConnected) {
      console.log('[LiveKit] Disconnecting...');
      room.disconnect();
      // State will be reset in handleDisconnected event
    }
  }, [room, isConnected]);

  // Enable/disable microphone
  const setMicEnabled = useCallback(async (enabled: boolean) => {
    if (!room) return;

    try {
      await room.localParticipant.setMicrophoneEnabled(enabled);
      setMicEnabledState(enabled);
    } catch (err) {
      console.error('[LiveKit] Failed to toggle microphone:', err);
    }
  }, [room]);

  // Auto-connect if configured
  useEffect(() => {
    if (config.autoConnect && room && !isConnected && !isConnecting) {
      console.log('[LiveKit] Auto-connect triggered');
      connect();
    }
  }, [config.autoConnect, room, isConnected, isConnecting, connect]);

  return {
    room,
    isConnected,
    isConnecting,
    agentIsSpeaking,
    interimTranscript,
    transcript,
    agentResponse,
    error,
    connect,
    disconnect,
    setMicEnabled,
    micEnabled,
  };
}
