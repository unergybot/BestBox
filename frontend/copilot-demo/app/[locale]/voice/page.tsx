'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { LiveKitVoicePanel } from '@/components/LiveKitVoicePanel';
import { VoicePanel } from '@/components/VoicePanel';
import { VoiceButton } from '@/components/VoiceButton';
import { ChatMessagesProvider, useChatMessages as useVoiceChatMessages } from '@/contexts/ChatMessagesContext';
import { detectTroubleshootingResults } from '@/lib/troubleshooting-detector';
import { TroubleshootingCard } from '@/components/troubleshooting';
import React, { useMemo } from 'react';

import { TroubleshootingIssue } from "@/types/troubleshooting";

function TroubleshootingCardsOverlay() {
  const { messages } = useVoiceChatMessages();

  const allResults = useMemo(() => {
    const results: TroubleshootingIssue[] = [];

    console.log("=== Voice TroubleshootingCardsOverlay Debug ===");
    console.log("messages:", messages);

    if (!messages || !Array.isArray(messages)) {
      return results;
    }

    for (const msg of messages) {
      if (msg && typeof msg === "object" && "content" in msg) {
        const content = typeof msg.content === "string" ? msg.content : "";
        if (content) {
          const detected = detectTroubleshootingResults(content);
          const issues = detected
            .filter((r): r is TroubleshootingIssue => r.result_type === "specific_solution")
            .map(r => r as TroubleshootingIssue);
          results.push(...issues);
        }
      }
    }
    console.log("Total results:", results.length);
    return results;
  }, [messages]);

  if (allResults.length === 0) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 max-w-md max-h-96 overflow-y-auto space-y-4 z-50 pointer-events-none">
      {allResults.map((result, index) => (
        <div key={result.case_id || index} className="pointer-events-auto">
          <TroubleshootingCard data={result} />
        </div>
      ))}
    </div>
  );
}

export default function VoicePage() {
  const t = useTranslations('Voice');
  const [mode, setMode] = useState<'panel' | 'button'>('panel');
  const [token, setToken] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [isLoadingToken, setIsLoadingToken] = useState(false);

  const useLiveKit = process.env.NEXT_PUBLIC_USE_LIVEKIT === 'true';
  const liveKitUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL || 'ws://localhost:7880';

  useEffect(() => {
    if (!useLiveKit) return;

    async function fetchToken() {
      setIsLoadingToken(true);
      setTokenError(null);

      try {
        const roomName = `bestbox-voice-${Date.now()}`;

        try {
          console.log('[Voice Page] Dispatching agent to room...');
          await fetch('/api/livekit/dispatch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ roomName }),
          });
          console.log('[Voice Page] Agent dispatch requested');
          await new Promise(resolve => setTimeout(resolve, 2000));
        } catch (dispatchError) {
          console.warn('[Voice Page] Agent dispatch failed:', dispatchError);
        }
        
        console.log('[Voice Page] Requesting user token...');
        const response = await fetch('/api/livekit/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            roomName,
            participantName: `user-${Date.now()}`,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to get token: ${response.statusText}`);
        }

        const data = await response.json();
        setToken(data.token);
      } catch (error) {
        console.error('[Voice Page] Token fetch error:', error);
        setTokenError(error instanceof Error ? error.message : 'Failed to get LiveKit token');
      } finally {
        setIsLoadingToken(false);
      }
    }

    fetchToken();
  }, [useLiveKit]);

  return (
    <ChatMessagesProvider>
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="mb-8">
            <Link href="/" className="text-blue-600 hover:text-blue-800 text-sm mb-4 inline-block">
              ← 返回主页
            </Link>
            <h1 className="text-4xl font-bold text-gray-900 mb-2">
              {useLiveKit ? '🎙️ LiveKit 语音助手' : '语音助手演示'}
            </h1>
            <p className="text-lg text-gray-600">
              {useLiveKit
                ? '使用 WebRTC 实时语音与 BestBox 智能助手对话'
                : '使用语音与 BestBox 智能助手进行对话'
              }
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-6">
            {useLiveKit ? (
              <>
                {isLoadingToken && (
                  <div className="text-center py-12">
                    <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                    <p className="mt-4 text-gray-600">正在连接 LiveKit 服务...</p>
                  </div>
                )}

                {tokenError && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                    <h3 className="font-semibold text-red-800 mb-2">❌ 连接失败</h3>
                    <p className="text-sm text-red-700 mb-4">{tokenError}</p>
                    <button onClick={() => window.location.reload()} className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg">
                      重新尝试
                    </button>
                  </div>
                )}

                {token && !isLoadingToken && (
                  <div className="h-[600px]">
                    <LiveKitVoicePanel
                      serverUrl={liveKitUrl}
                      token={token}
                      title="BestBox 语音助手"
                      autoConnect={false}
                      className="h-full"
                    />
                  </div>
                )}
              </>
            ) : (
              <div className="flex justify-center">
                <VoicePanel serverUrl="ws://localhost:8765/ws/s2s" language="zh" title="BestBox 语音助手" showTextInput={true} />
              </div>
            )}
          </div>

          <TroubleshootingCardsOverlay />
        </div>
      </div>
    </ChatMessagesProvider>
  );
}
