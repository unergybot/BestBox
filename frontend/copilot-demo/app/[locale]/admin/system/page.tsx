"use client";

import { useEffect, useState, useCallback } from "react";
import { useTranslations } from "next-intl";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface Service {
  name: string;
  display_name: string;
  port: number;
  status: "running" | "stopped" | "error" | "starting" | "stopping" | "unknown";
  description: string;
  pid?: number;
  last_check?: string;
  manageable?: boolean;
  health_details?: {
    healthy?: boolean;
    status_code?: number;
    error?: string;
    response_text?: string;
  };
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("admin_jwt_token") || localStorage.getItem("admin_token") || "";
  if (!token) return {};
  if (token.includes(".")) return { Authorization: `Bearer ${token}` };
  return { "admin-token": token };
}

function ServiceStatusBadge({ status }: { status: Service["status"] }) {
  const t = useTranslations("AdminNew.serviceStatus");

  const colors: Record<string, string> = {
    running: "bg-green-100 text-green-800 border-green-200",
    stopped: "bg-gray-100 text-gray-600 border-gray-200",
    error: "bg-red-100 text-red-800 border-red-200",
    starting: "bg-yellow-100 text-yellow-800 border-yellow-200",
    stopping: "bg-orange-100 text-orange-800 border-orange-200",
    unknown: "bg-gray-100 text-gray-500 border-gray-200",
  };

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium border ${colors[status] || colors.unknown}`}>
      {t(status as any)}
    </span>
  );
}

function ServiceCard({
  service,
  onAction,
  isLoading,
}: {
  service: Service;
  onAction: (name: string, action: "start" | "stop" | "restart") => void;
  isLoading: boolean;
}) {
  const t = useTranslations("AdminNew.system");

  const isManageable = service.manageable !== false;
  const canStart = isManageable && (service.status === "stopped" || service.status === "error" || service.status === "unknown");
  const canStop = isManageable && (service.status === "running" || service.status === "error");
  const canRestart = isManageable && service.status === "running";

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-gray-900">{service.display_name}</h3>
          <p className="text-xs text-gray-500 mt-0.5">{service.description}</p>
        </div>
        <ServiceStatusBadge status={service.status} />
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm mb-4">
        <div>
          <span className="text-gray-500">{t("port")}:</span>{" "}
          <span className="font-mono text-gray-700">{service.port}</span>
        </div>
        {service.pid ? (
          <div>
            <span className="text-gray-500">{t("pid")}:</span>{" "}
            <span className="font-mono text-gray-700">{service.pid}</span>
          </div>
        ) : null}
      </div>

      {service.health_details?.error ? (
        <div className="text-xs text-red-600 bg-red-50 p-2 rounded mb-3">
          {service.health_details.error}
        </div>
      ) : null}

      {isManageable ? (
      <div className="flex gap-2">
        {canStart ? (
          <button
            onClick={() => onAction(service.name, "start")}
            disabled={isLoading}
            className="flex-1 px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {t("start")}
          </button>
        ) : null}

        {canStop ? (
          <button
            onClick={() => onAction(service.name, "stop")}
            disabled={isLoading}
            className="flex-1 px-3 py-1.5 bg-red-600 text-white text-sm rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {t("stop")}
          </button>
        ) : null}

        {canRestart ? (
          <button
            onClick={() => onAction(service.name, "restart")}
            disabled={isLoading}
            className="flex-1 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {t("restart")}
          </button>
        ) : null}
      </div>
      ) : (
      <div className="text-xs text-gray-400 italic">
        {t("externalService")}
      </div>
      )}
    </div>
  );
}

export default function SystemPage() {
  const t = useTranslations("AdminNew.system");
  const tCommon = useTranslations("AdminNew.common");

  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const fetchServices = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/services`, {
        headers: getAuthHeaders(),
      });

      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          throw new Error(t("accessDenied"));
        }
        throw new Error(`Failed to fetch services: ${res.status}`);
      }

      const data = await res.json();
      setServices(data.services || []);
      setLastRefresh(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch services");
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchServices();

    const interval = setInterval(fetchServices, 5000);
    return () => clearInterval(interval);
  }, [fetchServices]);

  const handleServiceAction = async (
    serviceName: string,
    action: "start" | "stop" | "restart"
  ) => {
    setActionLoading(serviceName);

    try {
      const res = await fetch(`${API_BASE}/admin/services/${serviceName}/${action}`, {
        method: "POST",
        headers: getAuthHeaders(),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Failed to ${action} service`);
      }

      await fetchServices();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} service`);
    } finally {
      setActionLoading(null);
    }
  };

  const runningCount = services.filter((s) => s.status === "running").length;
  const stoppedCount = services.filter((s) => s.status === "stopped").length;
  const errorCount = services.filter((s) => s.status === "error").length;

  return (
    <div className="p-6">
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{t("title")}</h1>
            <p className="text-gray-600 mt-1">{t("subtitle")}</p>
          </div>
          <button
            onClick={fetchServices}
            disabled={loading}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            <svg
              className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            {t("refresh")}
          </button>
        </div>
      </header>

      {error ? (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      ) : null}

      <div className="mb-6 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-blue-900">{t("advancedMonitoring")}</h3>
            <p className="text-sm text-blue-700 mt-1">
              {t("advancedMonitoringDesc")}
            </p>
          </div>
          <a
            href="http://localhost:8086"
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            {t("openStatusPage")}
          </a>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <div className="text-sm text-gray-500 mb-1">{t("totalServices")}</div>
          <div className="text-3xl font-bold text-gray-900">{services.length}</div>
        </div>
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <div className="text-sm text-gray-500 mb-1">{t("running")}</div>
          <div className="text-3xl font-bold text-green-600">{runningCount}</div>
        </div>
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <div className="text-sm text-gray-500 mb-1">{t("stopped")}</div>
          <div className="text-3xl font-bold text-gray-600">{stoppedCount}</div>
        </div>
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <div className="text-sm text-gray-500 mb-1">{t("errors")}</div>
          <div className="text-3xl font-bold text-red-600">{errorCount}</div>
        </div>
      </div>

      {loading && services.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <div className="animate-pulse">{tCommon("loading")}</div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {services.map((service) => (
              <ServiceCard
                key={service.name}
                service={service}
                onAction={handleServiceAction}
                isLoading={actionLoading === service.name}
              />
            ))}
          </div>

          <div className="mt-6 text-center text-sm text-gray-400">
            {t("lastUpdated")} {lastRefresh.toLocaleTimeString()}
            <br />
            {t("autoRefresh")}
          </div>
        </>
      )}
    </div>
  );
}
