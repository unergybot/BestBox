/**
 * useServiceHealth - React hook for monitoring BestBox service health
 *
 * Polls health endpoints for all services and returns real-time status.
 * Services monitored:
 * - LLM (llama-server): :8080/health
 * - Embeddings (BGE-M3): :8081/health
 * - Reranker (BGE-reranker): :8082/health
 * - S2S Gateway: :8765/health
 * - Qdrant: :6333/health
 */

import { useCallback, useState, useEffect, useRef } from 'react';

export type ServiceStatus = 'healthy' | 'degraded' | 'offline' | 'checking';

export interface ServiceHealth {
  name: string;
  status: ServiceStatus;
  details?: string;
  latency?: number; // ms
  timestamp?: number;
}

export interface ServiceHealthMap {
  llm: ServiceHealth;
  embeddings: ServiceHealth;
  reranker: ServiceHealth;
  s2s: ServiceHealth;
  qdrant: ServiceHealth;
}

export interface UseServiceHealthOptions {
  /** Polling interval in milliseconds (default: 10000) */
  pollInterval?: number;
  /** Request timeout in milliseconds (default: 2000) */
  timeout?: number;
  /** Auto-start polling on mount (default: true) */
  autoStart?: boolean;
  /** Callback when health changes */
  onChange?: (health: ServiceHealthMap) => void;
}

const DEFAULT_POLL_INTERVAL = 10000; // 10 seconds
const DEFAULT_TIMEOUT = 5000; // 5 seconds

// Get base URL for API calls
const getBaseUrl = () => {
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    return `${protocol}//${hostname}`;
  }
  return 'http://localhost';
};

// Service endpoint configurations
// Service endpoint configurations
const SERVICE_ENDPOINTS = {
  llm: { path: '/api/proxy/llm/health', name: 'LLM (Qwen2.5-14B)' },
  embeddings: { path: '/api/proxy/embeddings/health', name: 'Embeddings (BGE-M3)' },
  reranker: { path: '/api/proxy/reranker/health', name: 'Reranker (BGE-reranker)' },
  s2s: { path: '/api/proxy/s2s/health', name: 'S2S Gateway' },
  qdrant: { path: '/api/proxy/qdrant/healthz', name: 'Qdrant Vector Store' },
} as const;

type ServiceKey = keyof typeof SERVICE_ENDPOINTS;

export function useServiceHealth(options: UseServiceHealthOptions = {}): {
  health: ServiceHealthMap;
  isPolling: boolean;
  startPolling: () => void;
  stopPolling: () => void;
  refresh: () => Promise<void>;
} {
  const {
    pollInterval = DEFAULT_POLL_INTERVAL,
    timeout = DEFAULT_TIMEOUT,
    autoStart = true,
    onChange,
  } = options;

  // Initial state - all services checking
  const getInitialHealth = (): ServiceHealthMap => ({
    llm: { name: SERVICE_ENDPOINTS.llm.name, status: 'checking' },
    embeddings: { name: SERVICE_ENDPOINTS.embeddings.name, status: 'checking' },
    reranker: { name: SERVICE_ENDPOINTS.reranker.name, status: 'checking' },
    s2s: { name: SERVICE_ENDPOINTS.s2s.name, status: 'checking' },
    qdrant: { name: SERVICE_ENDPOINTS.qdrant.name, status: 'checking' },
  });

  const [health, setHealth] = useState<ServiceHealthMap>(getInitialHealth());
  const [isPolling, setIsPolling] = useState(false);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const onChangeRef = useRef(onChange);

  // Update onChange ref
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  /**
   * Check health of a single service
   */
  const checkServiceHealth = async (key: ServiceKey): Promise<ServiceHealth> => {
    const endpoint = SERVICE_ENDPOINTS[key];
    // Use proxy path relative to current origin
    const url = endpoint.path;
    const startTime = Date.now();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const response = await fetch(url, {
        method: 'GET',
        signal: controller.signal,
        cache: 'no-store',
      });

      clearTimeout(timeoutId);
      const latency = Date.now() - startTime;

      if (!response.ok) {
        return {
          name: endpoint.name,
          status: 'offline',
          details: `HTTP ${response.status}`,
          latency,
          timestamp: Date.now(),
        };
      }

      // Parse response to get detailed status
      const responseText = await response.text();
      let data: any = {};

      try {
        if (responseText) {
          data = JSON.parse(responseText);
        }
      } catch {
        // Ignore JSON parse errors
      }

      // Qdrant /healthz returns plain text "healthz check passed"
      if (key === 'qdrant' && responseText.includes('healthz check passed')) {
        return {
          name: endpoint.name,
          status: 'healthy',
          details: `${latency}ms`,
          latency,
          timestamp: Date.now(),
        };
      }

      // S2S specific: treat explicit reachability signals as authoritative
      if (key === 's2s' && (data.ok === false || data.reachable === false)) {
        return {
          name: endpoint.name,
          status: 'offline',
          details: data.message || 'Not reachable',
          latency,
          timestamp: Date.now(),
        };
      }

      // S2S specific: check TTS status
      if (key === 's2s' && data.tts_enabled === false) {
        return {
          name: endpoint.name,
          status: 'degraded',
          details: 'ASR only (TTS disabled)',
          latency,
          timestamp: Date.now(),
        };
      }

      // Qdrant specific: check if it reports unhealthy (JSON response)
      if (key === 'qdrant' && data.status && data.status !== 'ok') {
        return {
          name: endpoint.name,
          status: 'degraded',
          details: data.status || 'Unhealthy',
          latency,
          timestamp: Date.now(),
        };
      }

      // All good
      return {
        name: endpoint.name,
        status: 'healthy',
        details: data.message || `${latency}ms`,
        latency,
        timestamp: Date.now(),
      };
    } catch (error) {
      // Timeout or network error
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      return {
        name: endpoint.name,
        status: 'offline',
        details: errorMessage.includes('aborted') ? 'Timeout' : 'Connection failed',
        timestamp: Date.now(),
      };
    }
  };

  /**
   * Check health of all services
   */
  const checkAllServices = useCallback(async (): Promise<ServiceHealthMap> => {
    const keys: ServiceKey[] = ['llm', 'embeddings', 'reranker', 's2s', 'qdrant'];

    // Check all services in parallel
    const results = await Promise.all(keys.map(key => checkServiceHealth(key)));

    const healthMap: ServiceHealthMap = {
      llm: results[0],
      embeddings: results[1],
      reranker: results[2],
      s2s: results[3],
      qdrant: results[4],
    };

    return healthMap;
  }, [timeout]);

  /**
   * Refresh health status (manual trigger)
   */
  const refresh = useCallback(async () => {
    const newHealth = await checkAllServices();
    setHealth(newHealth);
    onChangeRef.current?.(newHealth);
  }, [checkAllServices]);

  /**
   * Start polling
   */
  const startPolling = useCallback(() => {
    if (pollTimerRef.current) {
      return; // Already polling
    }

    setIsPolling(true);

    // Immediate first check
    refresh();

    // Set up interval
    pollTimerRef.current = setInterval(() => {
      refresh();
    }, pollInterval);
  }, [refresh, pollInterval]);

  /**
   * Stop polling
   */
  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setIsPolling(false);
  }, []);

  // Auto-start on mount if enabled
  useEffect(() => {
    if (autoStart) {
      startPolling();
    }

    // Cleanup on unmount
    return () => {
      stopPolling();
    };
  }, []); // Empty deps - only run on mount/unmount

  return {
    health,
    isPolling,
    startPolling,
    stopPolling,
    refresh,
  };
}
