import { InputProps } from '@copilotkit/react-ui';
import { VoiceButton } from './VoiceButton';
import { useLocale } from 'next-intl';
import { useState, useRef, useCallback } from 'react';
import { useCopilotChat } from "@copilotkit/react-core";
import { TextMessage, MessageRole } from "@copilotkit/runtime-client-gql";
import { LiveKitVoiceButton } from './LiveKitVoiceButton';

export function VoiceInput(props: InputProps) {
    const [text, setText] = useState('');
    const [interimTranscript, setInterimTranscript] = useState('');
    const [isSpeaking, setIsSpeaking] = useState(false);
    const locale = useLocale();
    const inputRef = useRef<HTMLTextAreaElement>(null);

    // key is optional but good practice if multiple chat instances exist,
    // but here we just want the default context.
    const { appendMessage } = useCopilotChat();

    const handleSend = () => {
        if (text.trim()) {
            props.onSend(text);
            setText('');
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleInterimTranscript = useCallback((transcript: string) => {
        setInterimTranscript(transcript);
        setIsSpeaking(true);
    }, []);

    const handleTranscript = useCallback(async (transcript: string) => {
        if (!transcript) return;

        // Put final transcript in textarea for user to edit before sending
        setText(transcript);
        setInterimTranscript('');
        setIsSpeaking(false);

        // Focus textarea so user can immediately edit or press Enter to send
        inputRef.current?.focus();
    }, []);

    const handleResponse = useCallback(async (response: string) => {
        if (!response) return;

        await appendMessage(
            new TextMessage({
                role: MessageRole.Assistant,
                content: response,
            })
        );
    }, [appendMessage]);

    const useLiveKit = process.env.NEXT_PUBLIC_USE_LIVEKIT === 'true';

    return (
        <div className="p-4 border-t border-gray-100 bg-white">
            <div className="flex items-end gap-2 bg-gray-50 p-2 rounded-xl border border-gray-200 focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-500 transition-all">

                {/* Voice S2S Button (Integrated) */}
                <div className="flex-shrink-0 mb-1">
                    {useLiveKit ? (
                        <LiveKitVoiceButton
                            size="sm"
                            showText={false}
                            onInterimTranscript={handleInterimTranscript}
                            onTranscript={handleTranscript}
                            onResponse={handleResponse}
                        />
                    ) : (
                        <VoiceButton
                            language={locale}
                            size="sm"
                            showText={false}
                            onInterimTranscript={handleInterimTranscript}
                            onTranscript={handleTranscript}
                            onResponse={handleResponse}
                        />
                    )}
                </div>

                {/* Text Area with Interim Transcript Overlay */}
                <div className="relative flex-grow min-h-[44px] flex items-center">
                    <textarea
                        ref={inputRef}
                        className="w-full bg-transparent border-none focus:ring-0 p-0 text-gray-900 placeholder-gray-400 resize-none h-24"
                        placeholder={isSpeaking ? '' : 'Type a message or use voice...'}
                        value={text}
                        onChange={(e) => {
                            setText(e.target.value);
                            // Clear interim transcript if user starts typing
                            if (interimTranscript) {
                                setInterimTranscript('');
                                setIsSpeaking(false);
                            }
                        }}
                        onKeyDown={handleKeyDown}
                        disabled={props.inProgress}
                    />
                    {/* Interim transcript overlay */}
                    {isSpeaking && interimTranscript && !text && (
                        <div className="absolute inset-0 pointer-events-none p-2 text-gray-400 italic overflow-hidden">
                            {interimTranscript}...
                        </div>
                    )}
                </div>

                {/* Send Button */}
                <button
                    onClick={handleSend}
                    disabled={!text.trim() || props.inProgress}
                    className={`
            flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all mb-1
            ${text.trim() && !props.inProgress
                            ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-md'
                            : 'bg-gray-200 text-gray-400 cursor-not-allowed'}
          `}
                >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
                        <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                    </svg>
                </button>
            </div>
        </div>
    );
}
