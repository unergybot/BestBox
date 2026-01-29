"use client";

import { useCopilotChat } from "@copilotkit/react-core";
import { MessageRole } from "@copilotkit/runtime-client-gql";
import { useEffect, useRef } from "react";
import { useS2S } from "@/hooks/useS2S";

export function CopilotTTS() {
    const { visibleMessages } = useCopilotChat();
    const { speak, isConnected } = useS2S();

    // Track the last processed message ID to avoid re-speaking
    const lastSpokenMessageIdRef = useRef<string | null>(null);
    // Track the length of text already spoken for the current message (streaming)
    const spokenLengthRef = useRef<number>(0);

    useEffect(() => {
        if (!isConnected || !visibleMessages || visibleMessages.length === 0) return;

        const lastMessage = visibleMessages[visibleMessages.length - 1];

        // Only speak Assistant messages
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const msg = lastMessage as any;
        if (msg.role !== MessageRole.Assistant) return;

        // TODO: Verify if CopilotKit supports unique IDs for messages we can track
        // If not, we might need a more heuristic approach or rely on index
        // Assuming 'id' exists or we use the object reference (less reliable for updates)
        const messageId = msg.id || `msg-${visibleMessages.length - 1}`;
        const content = typeof msg.content === 'string' ? msg.content : '';

        if (!content) return;

        // Check for [SPEECH] block using [\s\S] to match newlines (safe for older ES versions)
        const speechMatch = content.match(/\[SPEECH\]([\s\S]*?)(\[\/SPEECH\]|$)/);

        let textToSpeak = "";

        if (speechMatch) {
            // We have a speech block (partial or complete)
            textToSpeak = speechMatch[1];
        } else {
            // Backward compatibility: no speech block found yet
            // If the message is long enough and doesn't start with [SPEECH], speak it?
            // Or wait? Let's wait a bit to avoid speaking the tag itself if it comes late.
            // But usually LLM outputs it first.
            if (content.length > 10 && !content.startsWith("[")) {
                textToSpeak = content;
            }
        }

        // Determine new text to speak from the specific speech part
        if (textToSpeak) {
            const newText = textToSpeak.slice(spokenLengthRef.current);

            if (newText.length > 0) {
                console.log(`[CopilotTTS] Speaking chunk: "${newText}"`);
                speak(newText, false);
                spokenLengthRef.current = textToSpeak.length;
            }
        }

        // Stop speaking if [/SPEECH] is closed and we have processed it
        if (content.includes("[/SPEECH]") && spokenLengthRef.current >= (speechMatch ? speechMatch[1].length : 0)) {
            // We are done with the speech part.
        }

    }, [visibleMessages, isConnected, speak]);

    return null; // Headless component
}
