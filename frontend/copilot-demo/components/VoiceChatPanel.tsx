"use client";

import React, { useEffect, useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useLiveKitRoom } from "@/hooks/useLiveKitRoom";
import { ChatMessage } from "./ChatMessage";
import { VoiceControls } from "./VoiceControls";
import { TypingIndicator } from "./TypingIndicator";
import { useChatMessages } from "@/contexts/ChatMessagesContext";

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
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const {
        addMessage,
        updateLastAssistantMessage,
        clearMessages,
    } = useChatMessages();

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

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [transcript, agentResponse, agentIsSpeaking]);

    useEffect(() => {
        if (transcript) {
            addMessage("user", transcript);
        }
    }, [transcript, addMessage]);

    useEffect(() => {
        if (agentResponse) {
            updateLastAssistantMessage(agentResponse);
        }
    }, [agentResponse, updateLastAssistantMessage]);

    const handleClearChat = useCallback(() => {
        clearMessages();
    }, [clearMessages]);

    return (
        <div className="flex flex-col h-full bg-slate-50 overflow-hidden">
            <div className="bg-white px-6 py-4 flex items-center justify-between border-b border-slate-100 shadow-sm z-10">
                <h2 className="text-lg font-bold text-slate-800 tracking-tight">
                    {t("title")}
                </h2>
                <VoiceControls
                    micEnabled={micEnabled}
                    onToggleMic={() => setMicEnabled(!micEnabled)}
                    isTTSMuted={false}
                    onToggleTTS={() => {}}
                    onClearChat={handleClearChat}
                    isConnected={isConnected}
                />
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-6 scroll-smooth">
                <ChatMessagesContainer />
                {(agentIsSpeaking && !agentResponse) && <TypingIndicator />}
                <div ref={messagesEndRef} className="h-4" />
            </div>

            {error && (
                <div className="bg-rose-50 px-6 py-3 border-t border-rose-100">
                    <p className="text-xs text-rose-600 font-medium">{error}</p>
                </div>
            )}

            {!isConnected && !isConnecting && (
                <div className="px-6 py-4">
                    <button
                        onClick={() => connect()}
                        className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold text-sm shadow-md"
                    >
                        {t("title")}
                    </button>
                </div>
            )}
        </div>
    );
};

import { useChatMessages as useChatMessagesList } from "@/contexts/ChatMessagesContext";

function ChatMessagesContainer() {
    const { messages } = useChatMessagesList();
    const t = useTranslations("VoiceChat");

    if (messages.length === 0) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-center px-4 opacity-40">
                <div className="w-16 h-16 bg-slate-200 rounded-full flex items-center justify-center mb-4">
                    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                        <line x1="12" x2="12" y1="19" y2="22" />
                    </svg>
                </div>
                <p className="text-sm font-medium text-slate-500">{t("listening")}</p>
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {messages.map((msg) => (
                <ChatMessage
                    key={msg.id}
                    role={msg.role}
                    content={msg.content}
                    timestamp={msg.timestamp}
                />
            ))}
        </div>
    );
}
