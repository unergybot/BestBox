/**
 * useAudioCapture - React hook for capturing microphone audio
 * 
 * Captures PCM16 audio from the microphone at 16kHz for speech recognition.
 * Uses Web Audio API with ScriptProcessorNode for real-time processing.
 */

import { useCallback, useRef, useState, useEffect } from 'react';

export interface AudioCaptureOptions {
  /** Sample rate for recording (default: 16000 for Whisper) */
  sampleRate?: number;
  /** Callback when audio chunk is captured */
  onAudioChunk?: (chunk: ArrayBuffer) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
}

export interface AudioCaptureState {
  /** Whether currently recording */
  isRecording: boolean;
  /** Whether microphone permission is granted */
  hasPermission: boolean;
  /** Current audio level (0-1) for visualization */
  audioLevel: number;
  /** Error message if any */
  error: string | null;
}

export interface AudioCaptureControls {
  /** Start recording */
  startRecording: () => Promise<void>;
  /** Stop recording */
  stopRecording: () => void;
  /** Request microphone permission */
  requestPermission: () => Promise<boolean>;
}

export function useAudioCapture({
  sampleRate = 16000,
  onAudioChunk,
  onError,
}: AudioCaptureOptions = {}): AudioCaptureState & AudioCaptureControls {
  const [isRecording, setIsRecording] = useState(false);
  const [hasPermission, setHasPermission] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Refs for audio components
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Cleanup function
  const cleanup = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (analyserRef.current) {
      analyserRef.current.disconnect();
      analyserRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    setIsRecording(false);
    setAudioLevel(0);
  }, []);

  // Request permission
  const requestPermission = useCallback(async (): Promise<boolean> => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Microphone access is not available. Please ensure you are using HTTPS or localhost.');
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      stream.getTracks().forEach((track) => track.stop());
      setHasPermission(true);
      setError(null);
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Microphone access denied';
      setError(message);
      setHasPermission(false);
      onError?.(err instanceof Error ? err : new Error(message));
      return false;
    }
  }, [onError]);

  // Start recording
  const startRecording = useCallback(async () => {
    try {
      setError(null);

      // Get microphone stream
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Microphone access is not available. Please ensure you are using HTTPS or localhost.');
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      setHasPermission(true);
      mediaStreamRef.current = stream;

      // Create audio context
      const context = new AudioContext({ sampleRate });
      audioContextRef.current = context;

      // Create source from stream
      const source = context.createMediaStreamSource(stream);

      // Create analyser for level visualization
      const analyser = context.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;
      source.connect(analyser);

      // Create processor for audio capture
      // Using 4096 samples = ~256ms at 16kHz
      const processor = context.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (event) => {
        const inputData = event.inputBuffer.getChannelData(0);

        // Convert float32 to int16
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const sample = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = sample < 0 ? sample * 32768 : sample * 32767;
        }

        onAudioChunk?.(pcm16.buffer);
      };

      source.connect(processor);
      processor.connect(context.destination);

      // Start level monitoring
      const updateLevel = () => {
        if (analyserRef.current) {
          const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
          analyserRef.current.getByteFrequencyData(dataArray);

          // Calculate RMS level
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i] * dataArray[i];
          }
          const rms = Math.sqrt(sum / dataArray.length) / 255;
          setAudioLevel(rms);
        }
        animationFrameRef.current = requestAnimationFrame(updateLevel);
      };
      updateLevel();

      setIsRecording(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start recording';
      setError(message);
      onError?.(err instanceof Error ? err : new Error(message));
      cleanup();
    }
  }, [sampleRate, onAudioChunk, onError, cleanup]);

  // Stop recording
  const stopRecording = useCallback(() => {
    cleanup();
  }, [cleanup]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return {
    isRecording,
    hasPermission,
    audioLevel,
    error,
    startRecording,
    stopRecording,
    requestPermission,
  };
}
