"use client";

import React from "react";

interface ChatMessageProps {
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
    role,
    content,
    timestamp,
}) => {
    const isUser = role === "user";

    return (
        <div className={`flex w-full mb-4 ${isUser ? "justify-end" : "justify-start"}`}>
            <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm transition-all duration-300 hover:shadow-md ${isUser
                        ? "bg-indigo-600 text-white rounded-tr-none"
                        : "bg-white border border-slate-100 text-slate-800 rounded-tl-none"
                    }`}
            >
                <div className="flex items-center gap-2 mb-1.5 opacity-80">
                    <span className="text-lg">
                        {isUser ? (
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
                        ) : (
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 8V4H8" /><rect width="16" height="12" x="4" y="8" rx="2" /><path d="M2 14h2" /><path d="M20 14h2" /><path d="M15 13v2" /><path d="M9 13v2" /></svg>
                        )}
                    </span>
                    <span className="text-[10px] font-medium uppercase tracking-wider">
                        {timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                </div>
                <div className="text-sm leading-relaxed whitespace-pre-wrap">
                    {content}
                </div>
            </div>
        </div>
    );
};
