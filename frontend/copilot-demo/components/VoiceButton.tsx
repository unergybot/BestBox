'use client';

/**
 * VoiceButton - Push-to-talk voice interaction component
 *
 * Provides a microphone button for speech-to-speech interaction
 * with real-time visual feedback.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useS2S } from '@/hooks/useS2S';

/**
 * Play a beep sound for audio feedback
 * @param frequency - Frequency in Hz (e.g., 800 for high beep)
 * @param duration - Duration in ms
 * @param volume - Volume 0-1
 */
function playBeep(frequency: number, duration: number, volume: number = 0.3) {
  if (typeof window === 'undefined') return;

  try {
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    oscillator.frequency.value = frequency;
    oscillator.type = 'sine';

    gainNode.gain.setValueAtTime(volume, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration / 1000);

    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + duration / 1000);
  } catch (err) {
    console.error('Failed to play beep:', err);
  }
}

interface VoiceButtonProps {
  /** S2S server URL */
  serverUrl?: string;
  /** Recognition language */
  language?: string;
  /** Callback when user's speech is transcribed */
  onTranscript?: (text: string) => void;
  /** Callback when assistant responds */
  onResponse?: (text: string) => void;
  /** Callback for each response token (streaming) */
  onToken?: (token: string) => void;
  /** Show transcript/response text */
  showText?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Disabled state */
  disabled?: boolean;
}

// Mic icon SVG
const MicIcon = ({ className }: { className?: string }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <line x1="12" x2="12" y1="19" y2="22" />
  </svg>
);

// Mic off icon SVG
const MicOffIcon = ({ className }: { className?: string }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <line x1="2" x2="22" y1="2" y2="22" />
    <path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2" />
    <path d="M5 10v2a7 7 0 0 0 12 5" />
    <path d="M15 9.34V5a3 3 0 0 0-5.68-1.33" />
    <path d="M9 9v3a3 3 0 0 0 5.12 2.12" />
    <line x1="12" x2="12" y1="19" y2="22" />
  </svg>
);

// Volume/speaker icon SVG
const VolumeIcon = ({ className }: { className?: string }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
  </svg>
);

// Stop icon SVG
const StopIcon = ({ className }: { className?: string }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
  >
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </svg>
);

export function VoiceButton({
  serverUrl,
  language = 'zh',
  onTranscript,
  onResponse,
  onToken,
  showText = true,
  className = '',
  size = 'md',
  disabled = false,
}: VoiceButtonProps) {
  const [fullResponse, setFullResponse] = useState('');

  // Track full response with ref for callbacks
  const responseRef = useRef('');

  const {
    isConnected,
    isListening,
    isResponding,
    currentTranscript,
    currentResponse,
    audioLevel,
    error,
    connect,
    startListening,
    stopListening,
    interrupt,
    clear,
  } = useS2S({
    serverUrl,
    language,
    onAsrFinal: (text) => {
      console.log('VoiceButton: onAsrFinal', text);
      onTranscript?.(text);
      // Play a subtle beep to indicate transcription received
      playBeep(800, 100, 0.1);
    },
    onLlmToken: (token) => {
      onToken?.(token);
    },
    onResponseEnd: () => {
      const finalResponse = responseRef.current;
      console.log('VoiceButton: onResponseEnd', finalResponse);
      onResponse?.(finalResponse);
      // Play completion beep
      playBeep(600, 150, 0.15);
    },
    onError: (err) => {
      console.error('S2S Error:', err);
    },
    onConnectionChange: (connected) => {
      if (connected) {
        console.log('VoiceButton: Connected to S2S');
        // Play greeting beep when connected
        playBeep(1000, 200, 0.2);
      }
    },
  });

  // Track full response and sync ref
  useEffect(() => {
    setFullResponse(currentResponse);
    responseRef.current = currentResponse;
  }, [currentResponse]);

  // Handle button click
  const handleClick = useCallback(() => {
    if (disabled) return;

    if (isResponding) {
      // Interrupt current response
      interrupt();
    } else if (isListening) {
      // Stop listening
      stopListening();
    } else {
      // Start listening - connect first if not connected
      clear();
      setFullResponse('');
      if (!isConnected) {
        console.log('[VoiceButton] Connecting to S2S server...');
        connect();
        // Wait a moment for connection, then start listening
        setTimeout(() => {
          console.log('[VoiceButton] Starting listening after connect...');
          startListening();
        }, 1000);
      } else {
        startListening();
      }
    }
  }, [disabled, isResponding, isListening, isConnected, interrupt, stopListening, startListening, connect, clear]);

  // Size classes
  const sizeClasses = {
    sm: 'w-12 h-12',
    md: 'w-16 h-16',
    lg: 'w-20 h-20',
  };

  const iconSizeClasses = {
    sm: 'w-5 h-5',
    md: 'w-7 h-7',
    lg: 'w-9 h-9',
  };

  // Determine button state and appearance
  let buttonColor = 'bg-blue-500 hover:bg-blue-600';
  let Icon = MicIcon;
  let pulseClass = '';

  if (disabled) {
    buttonColor = 'bg-gray-400 cursor-not-allowed';
    Icon = MicOffIcon;
  } else if (isResponding) {
    buttonColor = 'bg-green-500 hover:bg-green-600';
    Icon = VolumeIcon;
    pulseClass = 'animate-pulse';
  } else if (isListening) {
    buttonColor = 'bg-red-500 hover:bg-red-600';
    Icon = StopIcon;
    pulseClass = 'animate-pulse';
  }

  // Audio level indicator style
  const levelStyle = isListening
    ? {
      transform: `scale(${1 + audioLevel * 0.5})`,
      opacity: 0.3 + audioLevel * 0.7,
    }
    : {};

  return (
    <div className={`flex flex-col items-center gap-3 ${className}`}>
      {/* Transcript display */}
      {showText && currentTranscript && (
        <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3 text-sm max-w-sm w-full">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">你说：</p>
          <p className="text-gray-900 dark:text-gray-100">{currentTranscript}</p>
        </div>
      )}

      {/* Response display */}
      {showText && currentResponse && (
        <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-3 text-sm max-w-sm w-full">
          <p className="text-xs text-blue-600 dark:text-blue-400 mb-1 flex items-center gap-1">
            <VolumeIcon className="w-3 h-3" />
            助手：
          </p>
          <p className="text-blue-900 dark:text-blue-100">{currentResponse}</p>
        </div>
      )}

      {/* Voice button with level indicator */}
      <div className="relative">
        {/* Audio level ring */}
        {isListening && (
          <div
            className="absolute inset-0 rounded-full bg-red-400 transition-transform duration-75"
            style={levelStyle}
          />
        )}

        {/* Main button */}
        <button
          onClick={handleClick}
          disabled={disabled}
          className={`
            relative ${sizeClasses[size]} rounded-full 
            flex items-center justify-center
            transition-all duration-200 shadow-lg
            ${buttonColor} ${pulseClass}
            focus:outline-none focus:ring-4 focus:ring-blue-300 dark:focus:ring-blue-800
          `}
          title={
            isResponding
              ? '点击停止'
              : isListening
                ? '点击结束录音'
                : '点击开始说话'
          }
        >
          <Icon className={`${iconSizeClasses[size]} text-white`} />
        </button>
      </div>

      {/* Status text */}
      <p className="text-xs text-gray-500 dark:text-gray-400">
        {isResponding
          ? '正在回复...'
          : isListening
            ? '正在听...'
            : '点击开始说话'}
      </p>

      {/* Connection status indicator */}
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'
            }`}
        />
        <span className="text-xs text-gray-400">
          {isConnected ? '已连接' : '未连接'}
        </span>
      </div>

      {/* Error display */}
      {error && (
        <p className="text-xs text-red-500 max-w-xs text-center">{error}</p>
      )}
    </div>
  );
}

export default VoiceButton;
