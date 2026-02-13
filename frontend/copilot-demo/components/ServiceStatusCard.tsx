"use client";

import { useServiceHealth, ServiceStatus } from '@/hooks/useServiceHealth';
import { useTranslations } from 'next-intl';

/**
 * ServiceStatusCard - Displays real-time health status of all BestBox services
 *
 * Shows color-coded indicators for:
 * - LLM (Qwen3-30B)
 * - Embeddings (BGE-M3)
 * - Reranker (BGE-reranker-v2-m3)
 * - S2S Gateway (ASR/TTS)
 * - Qdrant Vector Store
 */
export function ServiceStatusCard() {
  const t = useTranslations('Home.systemStatus');
  const { health, isPolling } = useServiceHealth({
    autoStart: true,
    pollInterval: 10000, // 10 seconds
  });

  /**
   * Get status indicator (emoji + color)
   */
  const getStatusIndicator = (status: ServiceStatus) => {
    switch (status) {
      case 'healthy':
        return { emoji: '🟢', color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200' };
      case 'degraded':
        return { emoji: '🟡', color: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' };
      case 'offline':
        return { emoji: '🔴', color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' };
      case 'checking':
        return { emoji: '⚪', color: 'text-gray-400', bg: 'bg-gray-50', border: 'border-gray-200' };
    }
  };

  /**
   * Get tooltip text for service status
   */
  const getTooltip = (key: keyof typeof health) => {
    const service = health[key];
    if (service.status === 'healthy') {
      return `${service.name}: Operational${service.latency ? ` (${service.latency}ms)` : ''}`;
    } else if (service.status === 'degraded') {
      return `${service.name}: ${service.details || 'Limited functionality'}`;
    } else if (service.status === 'offline') {
      return `${service.name}: ${service.details || 'Connection failed'}`;
    } else {
      return `${service.name}: Checking status...`;
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-semibold text-gray-800">
          {t('title')}
        </h2>
        {isPolling && (
          <span className="text-xs text-gray-500">
            Auto-refreshing every 10s
          </span>
        )}
      </div>

      {/* Service Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {/* LLM */}
        <div
          className={`rounded-lg p-4 border ${getStatusIndicator(health.llm.status).bg} ${getStatusIndicator(health.llm.status).border} transition-colors`}
          title={getTooltip('llm')}
        >
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="text-xs font-medium text-gray-600 mb-1">LLM</div>
              <div className="text-sm font-bold text-gray-900">Qwen3-30B</div>
            </div>
            <div className="text-2xl">{getStatusIndicator(health.llm.status).emoji}</div>
          </div>
          {health.llm.details && health.llm.status !== 'checking' && (
            <div className={`text-xs mt-2 ${getStatusIndicator(health.llm.status).color}`}>
              {health.llm.details}
            </div>
          )}
        </div>

        {/* Embeddings */}
        <div
          className={`rounded-lg p-4 border ${getStatusIndicator(health.embeddings.status).bg} ${getStatusIndicator(health.embeddings.status).border} transition-colors`}
          title={getTooltip('embeddings')}
        >
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="text-xs font-medium text-gray-600 mb-1">Embeddings</div>
              <div className="text-sm font-bold text-gray-900">BGE-M3</div>
            </div>
            <div className="text-2xl">{getStatusIndicator(health.embeddings.status).emoji}</div>
          </div>
          {health.embeddings.details && health.embeddings.status !== 'checking' && (
            <div className={`text-xs mt-2 ${getStatusIndicator(health.embeddings.status).color}`}>
              {health.embeddings.details}
            </div>
          )}
        </div>

        {/* Reranker */}
        <div
          className={`rounded-lg p-4 border ${getStatusIndicator(health.reranker.status).bg} ${getStatusIndicator(health.reranker.status).border} transition-colors`}
          title={getTooltip('reranker')}
        >
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="text-xs font-medium text-gray-600 mb-1">Reranker</div>
              <div className="text-sm font-bold text-gray-900">BGE-reranker</div>
            </div>
            <div className="text-2xl">{getStatusIndicator(health.reranker.status).emoji}</div>
          </div>
          {health.reranker.details && health.reranker.status !== 'checking' && (
            <div className={`text-xs mt-2 ${getStatusIndicator(health.reranker.status).color}`}>
              {health.reranker.details}
            </div>
          )}
        </div>

        {/* S2S Gateway */}
        <div
          className={`rounded-lg p-4 border ${getStatusIndicator(health.s2s.status).bg} ${getStatusIndicator(health.s2s.status).border} transition-colors`}
          title={getTooltip('s2s')}
        >
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="text-xs font-medium text-gray-600 mb-1">S2S Gateway</div>
              <div className="text-sm font-bold text-gray-900">Voice I/O</div>
            </div>
            <div className="text-2xl">{getStatusIndicator(health.s2s.status).emoji}</div>
          </div>
          {health.s2s.details && health.s2s.status !== 'checking' && (
            <div className={`text-xs mt-2 ${getStatusIndicator(health.s2s.status).color}`}>
              {health.s2s.details}
            </div>
          )}
        </div>

        {/* Qdrant */}
        <div
          className={`rounded-lg p-4 border ${getStatusIndicator(health.qdrant.status).bg} ${getStatusIndicator(health.qdrant.status).border} transition-colors`}
          title={getTooltip('qdrant')}
        >
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="text-xs font-medium text-gray-600 mb-1">Vector Store</div>
              <div className="text-sm font-bold text-gray-900">Qdrant</div>
            </div>
            <div className="text-2xl">{getStatusIndicator(health.qdrant.status).emoji}</div>
          </div>
          {health.qdrant.details && health.qdrant.status !== 'checking' && (
            <div className={`text-xs mt-2 ${getStatusIndicator(health.qdrant.status).color}`}>
              {health.qdrant.details}
            </div>
          )}
        </div>

        {/* Overall Status Summary */}
        <div className="rounded-lg p-4 border border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="text-xs font-medium text-gray-600 mb-1">Overall</div>
              <div className="text-sm font-bold text-gray-900">
                {Object.values(health).filter(s => s.status === 'healthy').length}/5 Healthy
              </div>
            </div>
            <div className="text-2xl">
              {Object.values(health).every(s => s.status === 'healthy') ? '✓' :
               Object.values(health).some(s => s.status === 'offline') ? '⚠️' : '🔧'}
            </div>
          </div>
          <div className="text-xs mt-2 text-gray-600">
            {Object.values(health).every(s => s.status === 'healthy')
              ? 'All systems operational'
              : Object.values(health).some(s => s.status === 'offline')
              ? 'Some services offline'
              : 'Limited functionality'}
          </div>
        </div>
      </div>

      {/* Warnings for critical services offline */}
      {health.llm.status === 'offline' && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="text-sm font-medium text-red-800">
            ⚠️ LLM server offline - Agent responses unavailable
          </div>
          <div className="text-xs text-red-600 mt-1">
            Run: <code className="bg-red-100 px-1 rounded">./scripts/start-llm.sh</code>
          </div>
        </div>
      )}

      {health.qdrant.status === 'offline' && (
        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="text-sm font-medium text-yellow-800">
            ⚠️ Qdrant offline - Knowledge search unavailable
          </div>
          <div className="text-xs text-yellow-600 mt-1">
            Run: <code className="bg-yellow-100 px-1 rounded">docker compose up -d</code>
          </div>
        </div>
      )}
    </div>
  );
}
