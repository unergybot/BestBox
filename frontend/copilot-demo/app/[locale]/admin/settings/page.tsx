"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface LLMConfig {
  provider: string;
  model: string;
  base_url: string;
  api_key_masked?: string;
  env_override_active: boolean;
  parameters: {
    temperature: number;
    max_tokens: number;
    streaming: boolean;
    max_retries: number;
  };
}

interface ModelOption {
  model_id: string;
  display_name: string;
  description?: string;
  is_recommended: boolean;
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token =
    localStorage.getItem("admin_jwt_token") ||
    localStorage.getItem("admin_token") ||
    "";
  if (!token) return {};
  if (token.includes(".")) return { Authorization: `Bearer ${token}` };
  return { "admin-token": token };
}

const PROVIDER_CONFIGS = {
  local_vllm: {
    name: "Local vLLM",
    description: "Run models on your own hardware (AMD ROCm / NVIDIA CUDA)",
    default_base_url: "http://localhost:8001/v1",
    requires_api_key: false,
  },
  nvidia: {
    name: "NVIDIA API",
    description: "Cloud inference via NVIDIA's API catalog",
    default_base_url: "https://integrate.api.nvidia.com/v1",
    requires_api_key: true,
  },
  openrouter: {
    name: "OpenRouter",
    description: "Access 100+ models through unified API",
    default_base_url: "https://openrouter.ai/api/v1",
    requires_api_key: true,
  },
} as const;

export default function SettingsPage() {
  const t = useTranslations("AdminNew.settings");

  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [provider, setProvider] = useState<keyof typeof PROVIDER_CONFIGS>("local_vllm");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);

  const [models, setModels] = useState<Array<ModelOption>>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [showCustomModel, setShowCustomModel] = useState(false);
  const [customModel, setCustomModel] = useState("");

  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(4096);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/settings/llm`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error("Failed to fetch config");

      const data: LLMConfig = await res.json();
      setConfig(data);
      setProvider(data.provider as keyof typeof PROVIDER_CONFIGS);
      setBaseUrl(data.base_url);
      setSelectedModel(data.model);
      setTemperature(data.parameters?.temperature ?? 0.7);
      setMaxTokens(data.parameters?.max_tokens ?? 4096);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load config");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchModels = useCallback(async (providerName: keyof typeof PROVIDER_CONFIGS) => {
    try {
      const res = await fetch(`${API_BASE}/admin/settings/llm/models/${providerName}`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error("Failed to fetch models");

      const data = await res.json();
      const list = (data.models || []) as Array<ModelOption>;
      setModels(list);

      // Auto-select first recommended model, or first model if none recommended
      if (list.length > 0) {
        const recommended = list.find((m) => m.is_recommended);
        setSelectedModel(recommended ? recommended.model_id : list[0].model_id);
      }
    } catch {
      setModels([]);
    }
  }, []);

  useEffect(() => {
    void fetchConfig();
  }, [fetchConfig]);

  useEffect(() => {
    if (provider) {
      void fetchModels(provider);
    }
  }, [provider, fetchModels]);

  const handleProviderChange = (nextProvider: keyof typeof PROVIDER_CONFIGS) => {
    setProvider(nextProvider);
    setBaseUrl(PROVIDER_CONFIGS[nextProvider].default_base_url);
    setApiKey("");
    setShowApiKey(false);
    setTestResult(null);
    setShowCustomModel(false);
    setSelectedModel("");
    setCustomModel("");
  };

  const selectedFinalModel = showCustomModel ? customModel.trim() : selectedModel;

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);

    try {
      const res = await fetch(`${API_BASE}/admin/settings/llm/test`, {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          provider,
          base_url: baseUrl,
          api_key: apiKey || undefined,
          model: selectedFinalModel,
          parameters: {
            temperature,
            max_tokens: maxTokens,
            streaming: true,
            max_retries: 2,
          },
        }),
      });

      const data = await res.json();
      setTestResult({ success: Boolean(data.success), message: data.message || "Unknown result" });
    } catch (err) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : "Test failed",
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!window.confirm(t("confirmUpdateMessage"))) {
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/admin/settings/llm`, {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          provider,
          base_url: baseUrl,
          api_key: apiKey || undefined,
          model: selectedFinalModel,
          parameters: {
            temperature,
            max_tokens: maxTokens,
            streaming: true,
            max_retries: 2,
          },
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to save config");
      }

      window.alert(t("configUpdated"));
      await fetchConfig();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save config");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-center py-12 text-gray-500">Loading...</div>
      </div>
    );
  }

  const providerConfig = PROVIDER_CONFIGS[provider];

  return (
    <div className="p-6 max-w-4xl">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">{t("title")}</h1>
        <p className="text-gray-600 mt-1">{t("subtitle")}</p>
      </header>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">{error}</div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">{t("llmConfig")}</h2>

        <div className="mb-6">
          <label className="block text-sm font-medium mb-3">{t("provider")}</label>
          <div className="space-y-2">
            {Object.entries(PROVIDER_CONFIGS).map(([key, item]) => (
              <div
                key={key}
                className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                  provider === key ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:bg-gray-50"
                }`}
                onClick={() => handleProviderChange(key as keyof typeof PROVIDER_CONFIGS)}
              >
                <div className="flex items-start gap-3">
                  <input type="radio" name="provider" checked={provider === key} readOnly className="mt-1" />
                  <div>
                    <strong className="block">{item.name}</strong>
                    <span className="text-gray-500 text-sm">{item.description}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mb-6">
          <label className="block text-sm font-medium mb-2">{t("model")}</label>
          <select
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            value={showCustomModel ? "custom" : selectedModel}
            onChange={(e) => {
              if (e.target.value === "custom") {
                setShowCustomModel(true);
              } else {
                setSelectedModel(e.target.value);
                setShowCustomModel(false);
              }
            }}
          >
            {models.map((m) => (
              <option key={m.model_id} value={m.model_id}>
                {m.display_name} {m.is_recommended ? "(Recommended)" : ""}
              </option>
            ))}
            <option value="custom">{t("customModel")}</option>
          </select>

          {showCustomModel && (
            <input
              type="text"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg mt-2"
              placeholder={t("enterModelName")}
              value={customModel}
              onChange={(e) => setCustomModel(e.target.value)}
            />
          )}
        </div>

        {providerConfig.requires_api_key && (
          <div className="mb-6">
            <label className="block text-sm font-medium mb-2">{t("apiKey")}</label>

            {config?.env_override_active ? (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="text-blue-700 text-sm">ℹ️ {t("envOverrideActive")}</div>
                <code className="text-xs block mt-1 text-blue-600">
                  {t("usingEnvVar", { var: `${provider.toUpperCase()}_API_KEY` })}
                </code>
              </div>
            ) : (
              <div className="relative">
                <input
                  type={showApiKey ? "text" : "password"}
                  className="w-full px-3 py-2 pr-20 border border-gray-300 rounded-lg"
                  placeholder={config?.api_key_masked || "sk-..."}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <button
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2 top-2 text-sm text-gray-500 hover:text-gray-700"
                >
                  {showApiKey ? t("hide") : t("show")}
                </button>
              </div>
            )}
          </div>
        )}

        <div className="mb-6">
          <label className="block text-sm font-medium mb-2">Base URL</label>
          <input
            type="text"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
          />
        </div>

        <div className="mb-6">
          <button onClick={() => setShowAdvanced(!showAdvanced)} className="text-sm text-blue-600 hover:text-blue-700">
            {showAdvanced ? "▼" : "▶"} {t("advancedParameters")}
          </button>

          {showAdvanced && (
            <div className="mt-3 space-y-4 pl-4">
              <div>
                <label className="block text-sm font-medium mb-2">{t("temperature")}</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  className="w-32 px-3 py-2 border border-gray-300 rounded-lg"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value || "0.7"))}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t("maxTokens")}</label>
                <input
                  type="number"
                  step="256"
                  min="256"
                  max="32768"
                  className="w-32 px-3 py-2 border border-gray-300 rounded-lg"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value || "4096", 10))}
                />
              </div>
            </div>
          )}
        </div>

        {testResult && (
          <div
            className={`mb-6 p-4 rounded-lg ${
              testResult.success ? "bg-green-50 border border-green-200 text-green-700" : "bg-red-50 border border-red-200 text-red-700"
            }`}
          >
            {testResult.message}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handleTestConnection}
            disabled={testing || !selectedFinalModel}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors"
          >
            {testing ? t("testing") : t("testConnection")}
          </button>

          <button
            onClick={handleSave}
            disabled={saving || !selectedFinalModel}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {saving ? t("saving") : t("saveConfiguration")}
          </button>
        </div>
      </div>
    </div>
  );
}
