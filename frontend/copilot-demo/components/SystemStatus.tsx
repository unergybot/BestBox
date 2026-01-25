'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, AlertCircle, Loader2 } from 'lucide-react';

interface ServiceStatus {
  name: string;
  url: string;
  status: 'up' | 'down' | 'degraded' | 'checking';
  latency?: number;
  lastChecked?: Date;
}

export function SystemStatus() {
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: 'LLM Server', url: 'http://localhost:8080/health', status: 'checking' },
    { name: 'Embeddings', url: 'http://localhost:8081/health', status: 'checking' },
    { name: 'Agent API', url: 'http://localhost:8000/health', status: 'checking' },
    { name: 'Qdrant', url: 'http://localhost:6333/health', status: 'checking' },
    { name: 'PostgreSQL', url: 'http://localhost:8000/health/db', status: 'checking' },
  ]);

  useEffect(() => {
    const checkHealth = async () => {
      const updated = await Promise.all(
        services.map(async (service) => {
          try {
            const start = Date.now();
            const response = await fetch(service.url, {
              signal: AbortSignal.timeout(5000),
              cache: 'no-cache'
            });
            const latency = Date.now() - start;

            return {
              ...service,
              status: response.ok ? 'up' : 'degraded',
              latency,
              lastChecked: new Date(),
            } as ServiceStatus;
          } catch (error) {
            return {
              ...service,
              status: 'down' as const,
              lastChecked: new Date(),
            };
          }
        })
      );
      setServices(updated);
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {services.map((service) => (
        <ServiceCard key={service.name} service={service} />
      ))}
    </div>
  );
}

function ServiceCard({ service }: { service: ServiceStatus }) {
  const statusConfig = {
    up: {
      icon: CheckCircle,
      color: 'text-green-500',
      bg: 'bg-green-50',
      border: 'border-green-200',
    },
    degraded: {
      icon: AlertCircle,
      color: 'text-yellow-500',
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
    },
    down: {
      icon: XCircle,
      color: 'text-red-500',
      bg: 'bg-red-50',
      border: 'border-red-200',
    },
    checking: {
      icon: Loader2,
      color: 'text-gray-400',
      bg: 'bg-gray-50',
      border: 'border-gray-200',
    },
  };

  const config = statusConfig[service.status];
  const Icon = config.icon;

  return (
    <div className={`p-4 rounded-lg border ${config.border} ${config.bg} transition-all`}>
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-medium text-gray-900 text-sm">{service.name}</h3>
        <Icon
          className={`${config.color} ${service.status === 'checking' ? 'animate-spin' : ''}`}
          size={20}
        />
      </div>

      <div className="space-y-1">
        {service.latency !== undefined && (
          <p className="text-xs text-gray-600">
            Latency: <span className="font-mono font-medium">{service.latency}ms</span>
          </p>
        )}

        <p className="text-xs text-gray-500 capitalize">
          {service.status === 'checking' ? 'Checking...' : service.status}
        </p>
      </div>
    </div>
  );
}
