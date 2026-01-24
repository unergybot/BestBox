'use client';

/**
 * Voice Demo Page - Speech-to-Speech interaction demo
 * 
 * Standalone page for testing voice interaction with BestBox agents.
 */

import { VoicePanel } from '@/components/VoicePanel';
import { VoiceButton } from '@/components/VoiceButton';
import { useState } from 'react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';

export default function VoicePage() {
  const t = useTranslations('Voice');
  const [mode, setMode] = useState<'panel' | 'button'>('panel');

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
            语音助手演示
          </h1>
          <p className="text-lg text-gray-600">
            使用语音与 BestBox 智能助手进行对话
          </p>
        </div>

        {/* Mode Selector */}
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

        {/* Demo Area */}
        <div className="bg-white rounded-xl shadow-lg p-6 flex justify-center">
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

        {/* Instructions */}
        <div className="bg-white rounded-xl shadow-lg p-6 mt-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">
            使用说明
          </h2>
          <div className="space-y-3 text-gray-600">
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
          </div>
        </div>

        {/* Example Queries */}
        <div className="bg-white rounded-xl shadow-lg p-6 mt-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">
            示例查询
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-blue-50 rounded-lg p-4">
              <h3 className="font-medium text-blue-800 mb-2">ERP 查询</h3>
              <ul className="text-sm text-blue-700 space-y-1">
                <li>• "本月销售额是多少？"</li>
                <li>• "库存不足的产品有哪些？"</li>
                <li>• "查看最近的采购订单"</li>
              </ul>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <h3 className="font-medium text-green-800 mb-2">CRM 查询</h3>
              <ul className="text-sm text-green-700 space-y-1">
                <li>• "今天有哪些客户跟进？"</li>
                <li>• "查看重点客户信息"</li>
                <li>• "最近的商机进展如何？"</li>
              </ul>
            </div>
            <div className="bg-orange-50 rounded-lg p-4">
              <h3 className="font-medium text-orange-800 mb-2">IT 运维</h3>
              <ul className="text-sm text-orange-700 space-y-1">
                <li>• "服务器状态如何？"</li>
                <li>• "最近有没有告警？"</li>
                <li>• "数据库性能报告"</li>
              </ul>
            </div>
            <div className="bg-purple-50 rounded-lg p-4">
              <h3 className="font-medium text-purple-800 mb-2">办公自动化</h3>
              <ul className="text-sm text-purple-700 space-y-1">
                <li>• "今天有什么会议？"</li>
                <li>• "待办事项有哪些？"</li>
                <li>• "帮我安排明天的日程"</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-gray-500 text-sm">
          <p>BestBox 语音演示 | 使用 faster-whisper + XTTS v2</p>
        </div>
      </div>
    </div>
  );
}
