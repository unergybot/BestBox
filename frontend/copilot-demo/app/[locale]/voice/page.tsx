'use client';

/**
 * Voice Demo Page - LiveKit-powered Speech-to-Speech interaction
 *
 * Provides real-time voice interaction with BestBox agents using LiveKit WebRTC.
 * Falls back to legacy S2S if LiveKit is not enabled.
 */

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { LiveKitVoicePanel } from '@/components/LiveKitVoicePanel';
import { VoicePanel } from '@/components/VoicePanel';
import { VoiceButton } from '@/components/VoiceButton';

export default function VoicePage() {
  const t = useTranslations('Voice');
  const [mode, setMode] = useState<'panel' | 'button'>('panel');
  const [token, setToken] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [isLoadingToken, setIsLoadingToken] = useState(false);

  // Check if LiveKit is enabled
  const useLiveKit = process.env.NEXT_PUBLIC_USE_LIVEKIT === 'true';
  const liveKitUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL || 'ws://localhost:7880';

  // Fetch LiveKit token on mount
  useEffect(() => {
    if (!useLiveKit) return;

    async function fetchToken() {
      setIsLoadingToken(true);
      setTokenError(null);

      try {
        // Use unique room name to avoid stale worker assignments
        const roomName = `bestbox-voice-${Date.now()}`;

        // First, dispatch agent to room and wait for it to be ready
        try {
          console.log('[Voice Page] Dispatching agent to room...');
          await fetch('/api/livekit/dispatch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ roomName }),
          });
          console.log('[Voice Page] Agent dispatch requested');
          
          // Wait for agent to join the room
          await new Promise(resolve => setTimeout(resolve, 2000));
          console.log('[Voice Page] Waited for agent to join');
        } catch (dispatchError) {
          console.warn('[Voice Page] Agent dispatch failed:', dispatchError);
          // Continue anyway - agent might already be there
        }
        
        // Get user token
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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/"
            className="text-blue-600 hover:text-blue-800 text-sm mb-4 inline-block"
          >
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
          {useLiveKit && (
            <div className="mt-2 flex items-center gap-2 text-sm">
              <span className="px-2 py-1 bg-green-100 text-green-700 rounded">
                低延迟模式
              </span>
              <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
                200-800ms 延迟
              </span>
              <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded">
                语义转折检测
              </span>
            </div>
          )}
        </div>

        {/* Mode Selector - Only show for legacy S2S */}
        {!useLiveKit && (
          <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-800">
              演示模式
            </h2>
            <div className="flex gap-4">
              <button
                onClick={() => setMode('panel')}
                className={`px-6 py-3 rounded-lg font-medium transition-all ${
                  mode === 'panel'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                完整面板
              </button>
              <button
                onClick={() => setMode('button')}
                className={`px-6 py-3 rounded-lg font-medium transition-all ${
                  mode === 'button'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                仅按钮
              </button>
            </div>
          </div>
        )}

        {/* Demo Area */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          {useLiveKit ? (
            // LiveKit Mode
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
                  <div className="text-sm text-red-600">
                    <p className="font-medium mb-2">请检查：</p>
                    <ul className="list-disc list-inside space-y-1">
                      <li>LiveKit 服务是否运行: <code className="bg-red-100 px-2 py-0.5 rounded">docker ps | grep livekit</code></li>
                      <li>环境变量是否配置: <code className="bg-red-100 px-2 py-0.5 rounded">NEXT_PUBLIC_LIVEKIT_URL</code></li>
                      <li>后端服务是否正常: <code className="bg-red-100 px-2 py-0.5 rounded">curl http://localhost:8000/health</code></li>
                    </ul>
                  </div>
                  <button
                    onClick={() => window.location.reload()}
                    className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
                  >
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
            // Legacy S2S Mode
            <div className="flex justify-center">
              {mode === 'panel' ? (
                <VoicePanel
                  serverUrl="ws://localhost:8765/ws/s2s"
                  language="zh"
                  title="BestBox 语音助手"
                  showTextInput={true}
                />
              ) : (
                <div className="py-8">
                  <VoiceButton
                    serverUrl="ws://localhost:8765/ws/s2s"
                    language="zh"
                    showText={true}
                    size="lg"
                    onTranscript={(text) => console.log('Transcript:', text)}
                    onResponse={(text) => console.log('Response:', text)}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Instructions */}
        <div className="bg-white rounded-xl shadow-lg p-6 mt-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">
            使用说明
          </h2>
          <div className="space-y-3 text-gray-600">
            {useLiveKit ? (
              // LiveKit Instructions
              <>
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                    1
                  </span>
                  <p>确保服务正在运行：
                    <code className="bg-gray-100 px-2 py-1 rounded ml-1">USE_LIVEKIT=true ./scripts/start-all-services.sh</code>
                  </p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                    2
                  </span>
                  <p>启动语音代理：
                    <code className="bg-gray-100 px-2 py-1 rounded ml-1">python services/livekit_agent.py dev</code>
                  </p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                    3
                  </span>
                  <p>点击 "Connect" 按钮连接到语音会话</p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                    4
                  </span>
                  <p>允许浏览器访问麦克风权限</p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                    5
                  </span>
                  <p>开始说话 - 助手会自动检测你的语音并实时回复（无需按按钮）</p>
                </div>
              </>
            ) : (
              // Legacy S2S Instructions
              <>
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                    1
                  </span>
                  <p>确保 S2S 服务正在运行：<code className="bg-gray-100 px-2 py-1 rounded">./scripts/start-s2s.sh</code></p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                    2
                  </span>
                  <p>点击麦克风按钮开始录音</p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                    3
                  </span>
                  <p>说话完毕后再次点击按钮，或等待自动检测</p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                    4
                  </span>
                  <p>助手会用语音回复，同时显示文字</p>
                </div>
              </>
            )}
          </div>

          {/* Tech info */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-500">
              {useLiveKit ? (
                <>
                  <strong>技术栈：</strong> LiveKit WebRTC + BestBox LangGraph + Qwen2.5-14B
                  <br />
                  <strong>延迟：</strong> ~200-800ms (端到端)
                  <br />
                  <strong>转折检测：</strong> 语义 ML 模型 (非基于静音)
                </>
              ) : (
                <>
                  <strong>技术栈：</strong> faster-whisper + XTTS v2 + WebSocket
                </>
              )}
            </p>
          </div>
        </div>

        {/* Example Queries */}
        <div className="bg-white rounded-xl shadow-lg p-6 mt-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">
            示例查询
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-blue-50 rounded-lg p-4">
              <h3 className="font-medium text-blue-800 mb-2">📊 ERP 查询</h3>
              <ul className="text-sm text-blue-700 space-y-1">
                <li>• "What are the top 5 vendors?"</li>
                <li>• "Check inventory levels"</li>
                <li>• "Show recent purchase orders"</li>
              </ul>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <h3 className="font-medium text-green-800 mb-2">👥 CRM 查询</h3>
              <ul className="text-sm text-green-700 space-y-1">
                <li>• "Tell me about customer ABC Corp"</li>
                <li>• "Show me the sales pipeline"</li>
                <li>• "Recent sales opportunities"</li>
              </ul>
            </div>
            <div className="bg-orange-50 rounded-lg p-4">
              <h3 className="font-medium text-orange-800 mb-2">⚙️ IT 运维</h3>
              <ul className="text-sm text-orange-700 space-y-1">
                <li>• "Check server status"</li>
                <li>• "Show me recent error logs"</li>
                <li>• "What's the system health?"</li>
              </ul>
            </div>
            <div className="bg-purple-50 rounded-lg p-4">
              <h3 className="font-medium text-purple-800 mb-2">📅 办公自动化</h3>
              <ul className="text-sm text-purple-700 space-y-1">
                <li>• "Show pending leave requests"</li>
                <li>• "What's on my calendar today?"</li>
                <li>• "Approve leave request for John"</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Performance Stats (LiveKit only) */}
        {useLiveKit && token && (
          <div className="bg-gradient-to-r from-green-50 to-blue-50 rounded-xl shadow-lg p-6 mt-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-800">
              ⚡ 性能优势
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-blue-600">5x</div>
                <div className="text-sm text-gray-600 mt-1">更低延迟</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-green-600">48kHz</div>
                <div className="text-sm text-gray-600 mt-1">立体声音质</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-purple-600">WebRTC</div>
                <div className="text-sm text-gray-600 mt-1">生产级协议</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-orange-600">ML</div>
                <div className="text-sm text-gray-600 mt-1">智能转折</div>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 text-center text-gray-500 text-sm">
          <p>
            BestBox 语音演示 |
            {useLiveKit ? ' LiveKit WebRTC + LangGraph' : ' faster-whisper + XTTS v2'}
          </p>
          <p className="mt-1">
            AMD Ryzen AI Max+ 395 | Radeon 8060S | ROCm 7.2.0
          </p>
        </div>
      </div>
    </div>
  );
}
