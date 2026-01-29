"use client";

import React from "react";

interface VoiceControlsProps {
    micEnabled: boolean;
    onToggleMic: () => void;
    isTTSMuted: boolean;
    onToggleTTS: () => void;
    onClearChat: () => void;
    isConnected: boolean;
}

export const VoiceControls: React.FC<VoiceControlsProps> = ({
    micEnabled,
    onToggleMic,
    isTTSMuted,
    onToggleTTS,
    onClearChat,
    isConnected,
}) => {
    return (
        <div className="flex items-center gap-3">
            {/* Microphone Toggle */}
            <button
                onClick={onToggleMic}
                disabled={!isConnected}
                className={`p-2.5 rounded-xl transition-all duration-300 ${micEnabled
                        ? "bg-indigo-100 text-indigo-600 hover:bg-indigo-200"
                        : "bg-rose-100 text-rose-600 hover:bg-rose-200"
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                title={micEnabled ? "Disable Microphone" : "Enable Microphone"}
            >
                {micEnabled ? (
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" x2="12" y1="19" y2="22" /></svg>
                ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="2" x2="22" y1="2" y2="22" /><path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2" /><path d="M5 10v2a7 7 0 0 0 12 5" /><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33" /><path d="M9 9v3a3 3 0 0 0 5.12 2.12" /><line x1="12" x2="12" y1="19" y2="22" /></svg>
                )}
            </button>

            {/* TTS Speaker Toggle */}
            <button
                onClick={onToggleTTS}
                className={`p-2.5 rounded-xl transition-all duration-300 ${!isTTSMuted
                        ? "bg-emerald-100 text-emerald-600 hover:bg-emerald-200"
                        : "bg-slate-100 text-slate-400 hover:bg-slate-200"
                    }`}
                title={isTTSMuted ? "Unmute Voice Output" : "Mute Voice Output"}
            >
                {!isTTSMuted ? (
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" /><path d="M15.54 8.46a5 5 0 0 1 0 7.07" /><path d="M19.07 4.93a10 10 0 0 1 0 14.14" /></svg>
                ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 5 6 9 2 9v6l4 4 5-14z" /><line x1="22" x2="16" y1="9" y2="15" /><line x1="16" x2="22" y1="9" y2="15" /></svg>
                )}
            </button>

            {/* Clear Chat */}
            <button
                onClick={onClearChat}
                className="p-2.5 rounded-xl bg-slate-100 text-slate-400 hover:bg-slate-200 hover:text-rose-500 transition-all duration-300"
                title="Clear conversation"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /><line x1="10" x2="10" y1="11" y2="17" /><line x1="14" x2="14" y1="11" y2="17" /></svg>
            </button>
        </div>
    );
};
