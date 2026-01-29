'use client';

/**
 * LiveKitVoiceButton - Push-to-talk/toggle button for LiveKit
 *
 * Adapts the LiveKit room to a simple button interface compatible with VoiceInput.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useLiveKitRoom } from '@/hooks/useLiveKitRoom';

interface LiveKitVoiceButtonProps {
    /** Server URL */
    serverUrl?: string;
    /** API Token */
    token?: string;
    /** Callback for interim/partial transcripts (real-time while speaking) */
    onInterimTranscript?: (text: string) => void;
    /** Callback when user's speech is finalized */
    onTranscript?: (text: string) => void;
    /** Callback when assistant responds */
    onResponse?: (text: string) => void;
    /** Show transcript/response text (popup) */
    showText?: boolean;
    /** Additional CSS classes */
    className?: string;
    /** Size variant */
    size?: 'sm' | 'md' | 'lg';
    /** Disabled state */
    disabled?: boolean;
}

// Icons (Same as VoiceButton)
const MicIcon = ({ className }: { className?: string }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
);

const MicOffIcon = ({ className }: { className?: string }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
        <line x1="2" x2="22" y1="2" y2="22" />
        <path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2" />
        <path d="M5 10v2a7 7 0 0 0 12 5" />
        <path d="M15 9.34V5a3 3 0 0 0-5.68-1.33" />
        <path d="M9 9v3a3 3 0 0 0 5.12 2.12" />
        <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
);

const VolumeIcon = ({ className }: { className?: string }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
);

const StopIcon = ({ className }: { className?: string }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={className}>
        <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
);

export function LiveKitVoiceButton({
    serverUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL || '',
    token = '', // Should be fetched from API if empty
    onInterimTranscript,
    onTranscript,
    onResponse,
    showText = true,
    className = '',
    size = 'md',
    disabled = false,
}: LiveKitVoiceButtonProps) {

    // Internal token state if not provided
    const [internalToken, setInternalToken] = useState(token);
    const [tokenError, setTokenError] = useState<string | null>(null);

    // Fetch token if needed
    useEffect(() => {
        if (!token && !internalToken) {
            fetch('/api/livekit/token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    roomName: 'default-room',
                    participantName: 'user-' + Math.floor(Math.random() * 1000)
                })
            })
                .then(res => {
                    if (!res.ok) throw new Error(res.statusText);
                    return res.json();
                })
                .then(data => {
                    if (data.token) {
                        console.log('[LiveKitVoiceButton] Token received:', data.token.substring(0, 20) + '...');
                        setInternalToken(data.token);
                    }
                    else setTokenError("Failed to get token");
                })
                .catch(err => {
                    console.error('[LiveKitVoiceButton] Token fetch error:', err);
                    setTokenError(err.message);
                });
        }
    }, [token, internalToken]);

    const {
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
        room,
    } = useLiveKitRoom({
        url: serverUrl,
        token: internalToken || '',
        autoConnect: false,
    });

    // Interim transcript callback (real-time while speaking)
    const lastInterimRef = useRef('');
    useEffect(() => {
        const trimmed = interimTranscript.trim();
        const lastTrimmed = lastInterimRef.current.trim();

        if (trimmed && trimmed !== lastTrimmed) {
            lastInterimRef.current = interimTranscript;
            onInterimTranscript?.(interimTranscript);
            console.log('[LiveKitVoiceButton] Calling onInterimTranscript with:', interimTranscript);
        }
    }, [interimTranscript, onInterimTranscript]);

    // Final transcript callback (when user stops speaking)
    const lastTranscriptRef = useRef('');
    useEffect(() => {
        const trimmed = transcript.trim();
        const lastTrimmed = lastTranscriptRef.current.trim();

        if (trimmed && trimmed !== lastTrimmed) {
            lastTranscriptRef.current = transcript;
            onTranscript?.(transcript);
            console.log('[LiveKitVoiceButton] Calling onTranscript with:', transcript);
        }
    }, [transcript, onTranscript]);

    // Response callback
    const lastResponseRef = useRef('');
    useEffect(() => {
        // Trim whitespace for comparison
        const trimmed = agentResponse.trim();
        const lastTrimmed = lastResponseRef.current.trim();

        // Call on ANY content change (even if same), as long as not empty
        // This ensures responses always reach CopilotKit
        if (trimmed && trimmed !== lastTrimmed) {
            lastResponseRef.current = agentResponse;
            onResponse?.(agentResponse);
            console.log('[LiveKitVoiceButton] Calling onResponse with:', agentResponse.substring(0, 50) + '...');
        }
    }, [agentResponse, onResponse]);


    // Handle button click
    const handleClick = useCallback(async () => {
        if (disabled) return;

        // Try to start audio context immediately on user gesture
        if (room) {
            try {
                await room.startAudio();
            } catch (e) {
                console.warn("Failed to start audio context:", e);
            }
        }

        if (isConnected) {
            // If connected but mic is off (e.g. permission denied initially or muted), try to enable it
            if (!micEnabled) {
                await setMicEnabled(true);
            } else {
                // If mic is on, disconnect (end session)
                disconnect();
            }
        } else {
            await connect();
        }
    }, [disabled, isConnected, micEnabled, connect, disconnect, setMicEnabled, room]);

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

    // State Styles
    let buttonColor = 'bg-blue-500 hover:bg-blue-600';
    let Icon = MicIcon;
    let pulseClass = '';

    if (disabled || tokenError) {
        buttonColor = 'bg-gray-400 cursor-not-allowed';
        Icon = MicOffIcon;
    } else if (agentIsSpeaking) {
        buttonColor = 'bg-green-500 hover:bg-green-600';
        Icon = VolumeIcon;
        pulseClass = 'animate-pulse';
    } else if (isConnected) {
        if (micEnabled) {
            // Connected and Listening
            buttonColor = 'bg-red-500 hover:bg-red-600';
            Icon = StopIcon;
            pulseClass = 'animate-pulse';
        } else {
            // Connected but Mic Muted/Disabled
            buttonColor = 'bg-yellow-500 hover:bg-yellow-600';
            Icon = MicOffIcon;
            pulseClass = '';
        }
    } else if (isConnecting) {
        buttonColor = 'bg-yellow-500';
        pulseClass = 'animate-pulse';
    }

    return (
        <div className={`flex flex-col items-center gap-3 ${className}`}>
            {/* Transcript Popup */}
            {showText && transcript && isConnected && (
                <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3 text-sm max-w-sm w-full absolute bottom-full mb-2 z-10 shadow-lg">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">LiveKit:</p>
                    <p className="text-gray-900 dark:text-gray-100">{transcript}</p>
                </div>
            )}

            {/* Response Popup */}
            {showText && agentResponse && isConnected && (
                <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-3 text-sm max-w-sm w-full absolute bottom-full mb-2 z-10 shadow-lg">
                    <p className="text-xs text-blue-600 dark:text-blue-400 mb-1 flex items-center gap-1">
                        <VolumeIcon className="w-3 h-3" />
                        Agent:
                    </p>
                    <p className="text-blue-900 dark:text-blue-100">{agentResponse}</p>
                </div>
            )}


            <div className="relative">
                {/* Ring animation */}
                {isConnected && (
                    <div className="absolute inset-0 rounded-full bg-red-400 opacity-30 animate-ping"></div>
                )}

                <button
                    onClick={handleClick}
                    disabled={disabled || !!tokenError}
                    className={`
            relative ${sizeClasses[size]} rounded-full
            flex items-center justify-center
            transition-all duration-200 shadow-lg
            ${buttonColor} ${pulseClass}
            focus:outline-none focus:ring-4 focus:ring-blue-300 dark:focus:ring-blue-800
          `}
                    title={
                        isConnected
                            ? (micEnabled ? "Disconnect LiveKit" : "Enable Microphone")
                            : "Connect LiveKit Voice"
                    }
                >
                    <Icon className={`${iconSizeClasses[size]} text-white`} />
                </button>
            </div>

            {/* Status text */}
            <p className="text-xs text-gray-500 dark:text-gray-400">
                {agentIsSpeaking ? 'Agent Speaking' :
                    isConnected ? (micEnabled ? 'Listening...' : 'Mic Disabled') :
                        isConnecting ? 'Connecting...' :
                            'LiveKit Voice'
                }
            </p>

            {/* Connection dot */}
            <div className="flex flex-col items-center gap-1">
                <div className="flex items-center gap-2">
                    <div
                        className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'}`}
                    />
                    <span className="text-xs text-gray-400">
                        {tokenError || error ? 'Error' : (isConnected ? 'Connected' : 'LiveKit Ready')}
                    </span>
                </div>
                {(tokenError || error) && (
                    <span className="text-[10px] text-red-500 max-w-[100px] text-center leading-tight">
                        {tokenError || error}
                    </span>
                )}
            </div>
        </div>

    );
}
