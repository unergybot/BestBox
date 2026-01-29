"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useLiveKitRoom } from "@/hooks/useLiveKitRoom";
import { ChatMessage } from "./ChatMessage";
import { VoiceControls } from "./VoiceControls";
import { TypingIndicator } from "./TypingIndicator";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
}

interface VoiceChatPanelProps {
    serverUrl: string;
    token: string;
    locale: string;
}

export const VoiceChatPanel: React.FC<VoiceChatPanelProps> = ({
    serverUrl,
    token,
    locale,
}) => {
    const t = useTranslations("VoiceChat");
    const [messages, setMessages] = useState<Message[]>([]);
    const [isTTSMuted, setIsTTSMuted] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Track transcript and response locally to avoid redundant message creation
    const lastTranscriptRef = useRef("");
    const currentAssistantMsgIdRef = useRef<string | null>(null);

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
        autoConnect: true,
    });

    // Auto-scroll to bottom when messages change or agent is speaking (streaming text)
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, agentResponse, agentIsSpeaking]);

    // Handle User Transcript
    useEffect(() => {
        if (transcript && transcript !== lastTranscriptRef.current) {
            lastTranscriptRef.current = transcript;

            setMessages((prev) => [
                ...prev,
                {
                    id: `user-${Date.now()}`,
                    role: "user",
                    content: transcript,
                    timestamp: new Date(),
                },
            ]);

            // Reset assistant message tracker for a new response
            currentAssistantMsgIdRef.current = null;
        }
    }, [transcript]);

    // Handle Assistant Response (Streaming)
    useEffect(() => {
        if (agentResponse) {
            setMessages((prev) => {
                const lastMsg = prev[prev.length - 1];

                if (lastMsg && lastMsg.role === "assistant" && lastMsg.id === currentAssistantMsgIdRef.current) {
                    // Update existing assistant message
                    return prev.map((msg) =>
                        msg.id === lastMsg.id ? { ...msg, content: agentResponse } : msg
                    );
                } else {
                    // Create new assistant message
                    const newId = `assistant-${Date.now()}`;
                    currentAssistantMsgIdRef.current = newId;
                    return [
                        ...prev,
                        {
                            id: newId,
                            role: "assistant",
                            content: agentResponse,
                            timestamp: new Date(),
                        },
                    ];
                }
            });
        }
    }, [agentResponse]);

    // Handle TTS Mute
    useEffect(() => {
        if (!room) return;

        // Find all audio elements attached to tracks and mute/unmute them
        room.remoteParticipants.forEach(participant => {
            participant.audioTrackPublications.forEach(pub => {
                const track = pub.track;
                if (track && (track as any)._audioElement) {
                    (track as any)._audioElement.muted = isTTSMuted;
                }
            });
        });
    }, [isTTSMuted, room]);

    const handleClearChat = useCallback(() => {
        setMessages([]);
        lastTranscriptRef.current = "";
        currentAssistantMsgIdRef.current = null;
    }, []);

    return (
        <div className="flex flex-col h-full bg-slate-50 overflow-hidden">
            {/* Header */}
            <div className="bg-white px-6 py-4 flex items-center justify-between border-b border-slate-100 shadow-sm z-10">
                <div>
                    <h2 className="text-lg font-bold text-slate-800 tracking-tight">
                        {t("title")}
                    </h2>
                    <div className="flex items-center gap-1.5 mt-0.5">
                        <div className={`w-2 h-2 rounded-full ${isConnecting ? "bg-amber-400 animate-pulse" :
                                isConnected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" :
                                    "bg-slate-300"
                            }`}></div>
                        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
                            {isConnecting ? t("connecting") : isConnected ? t("connected") : t("disconnected")}
                        </span>
                    </div>
                </div>

                <VoiceControls
                    micEnabled={micEnabled}
                    onToggleMic={() => setMicEnabled(!micEnabled)}
                    isTTSMuted={isTTSMuted}
                    onToggleTTS={() => setIsTTSMuted(!isTTSMuted)}
                    onClearChat={handleClearChat}
                    isConnected={isConnected}
                />
            </div>

            {/* Messages Scroll Area */}
            <div className="flex-1 overflow-y-auto px-6 py-6 scroll-smooth">
                {messages.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center text-center px-4 opacity-40">
                        <div className="w-16 h-16 bg-slate-200 rounded-full flex items-center justify-center mb-4 transition-transform hover:scale-110">
                            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" x2="12" y1="19" y2="22" /></svg>
                        </div>
                        <p className="text-sm font-medium text-slate-500">{t("listening")}</p>
                    </div>
                )}

                <div className="space-y-2">
                    {messages.map((msg) => (
                        <ChatMessage
                            key={msg.id}
                            role={msg.role}
                            content={msg.content}
                            timestamp={msg.timestamp}
                        />
                    ))}

                    {(agentIsSpeaking && !agentResponse) && <TypingIndicator />}
                </div>

                <div ref={messagesEndRef} className="h-4" />
            </div>

            {/* Footer Info */}
            {error && (
                <div className="bg-rose-50 px-6 py-3 border-t border-rose-100 flex items-center gap-2">
                    <svg className="text-rose-500 shrink-0" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" x2="12" y1="8" y2="12" /><line x1="12" x2="12.01" y1="16" y2="16" /></svg>
                    <p className="text-xs text-rose-600 font-medium">{error}</p>
                </div>
            )}

            {!isConnected && !isConnecting && (
                <div className="px-6 py-4">
                    <button
                        onClick={() => connect()}
                        className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-sm shadow-md transition-all active:scale-95"
                    >
                        {t("title")}
                    </button>
                </div>
            )}
        </div>
    );
};
