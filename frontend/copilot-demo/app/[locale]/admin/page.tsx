"use client";

import React, { useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import LanguageSwitcher from "../../../components/LanguageSwitcher";

type UploadResult = {
  status?: string;
  uploaded_filename?: string;
  saved_path?: string;
  case_id?: string;
  total_issues?: number;
  source_file?: string;
  indexed?: boolean;
  indexing?: unknown;
  output_dir?: string;
  detail?: string;
};

export default function AdminPage() {
  const t = useTranslations("Admin");
  const locale = useLocale();

  const [file, setFile] = useState<File | null>(null);
  const [indexIntoQdrant, setIndexIntoQdrant] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isProcessingSample, setIsProcessingSample] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);

  const agentApiBase = useMemo(
    () => process.env.NEXT_PUBLIC_AGENT_API_URL || "http://localhost:8000",
    []
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setResult(null);

    if (!file) {
      setResult({ detail: t("errors.noFile") });
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setIsSubmitting(true);
    try {
      const res = await fetch(
        `/api/proxy/agent/admin/troubleshooting/upload-xlsx?index=${indexIntoQdrant ? "true" : "false"}`,
        { method: "POST", body: formData }
      );

      // Handle non-JSON responses (e.g., when backend services are down)
      let json: UploadResult;
      try {
        json = (await res.json()) as UploadResult;
      } catch {
        // Response is not JSON - likely plain text error from proxy
        const text = await res.text().catch(() => "");
        setResult({
          detail: text || t("errors.serviceDown"),
        });
        return;
      }

      if (!res.ok) {
        setResult({ detail: json.detail || t("errors.failed") });
        return;
      }

      setResult(json);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : undefined;
      setResult({ detail: message || t("errors.failed") });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleProcessSample() {
    setResult(null);
    setIsProcessingSample(true);
    try {
      const res = await fetch(
        `/api/proxy/agent/admin/troubleshooting/process-sample?index=${indexIntoQdrant ? "true" : "false"}`,
        { method: "POST" }
      );

      // Handle non-JSON responses (e.g., when backend services are down)
      let json: UploadResult;
      try {
        json = (await res.json()) as UploadResult;
      } catch {
        // Response is not JSON - likely plain text error from proxy
        const text = await res.text().catch(() => "");
        setResult({
          detail: text || t("errors.serviceDown"),
        });
        return;
      }

      if (!res.ok) {
        setResult({ detail: json.detail || t("errors.failed") });
        return;
      }

      setResult(json);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : undefined;
      setResult({ detail: message || t("errors.failed") });
    } finally {
      setIsProcessingSample(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{t("title")}</h1>
            <p className="mt-1 text-gray-600">{t("subtitle")}</p>
          </div>
          <LanguageSwitcher />
        </div>

        <div className="mt-6 bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-800">{t("upload.title")}</h2>
          <p className="mt-1 text-sm text-gray-600">{t("upload.hint")}</p>

          <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
            <div>
              <input
                type="file"
                accept=".xlsx"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
              />
              {file && (
                <div className="mt-2 text-sm text-gray-600">
                  {t("upload.selected")}: <span className="font-medium">{file.name}</span>
                </div>
              )}
            </div>

            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={indexIntoQdrant}
                onChange={(e) => setIndexIntoQdrant(e.target.checked)}
              />
              {t("upload.index")}
            </label>

            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-700 disabled:opacity-50"
            >
              {isSubmitting ? t("upload.processing") : t("upload.submit")}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-gray-200">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">{t("upload.sampleTitle")}</h3>
            <p className="text-sm text-gray-600 mb-3">{t("upload.sampleHint")}</p>
            <button
              type="button"
              disabled={isProcessingSample}
              onClick={handleProcessSample}
              className="px-4 py-2 rounded-lg bg-teal-600 text-white font-semibold hover:bg-teal-700 disabled:opacity-50"
            >
              {isProcessingSample ? t("upload.processing") : t("upload.processSample")}
            </button>
          </div>
        </div>

        {/* Mold Reference Document Upload */}
        <div className="mt-6 bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-800">
            📄 Mold Reference Documents
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Upload PDF, DOCX, or PPTX documents for the Mold Knowledge Base. Images will be processed with OCR.
          </p>

          <div className="mt-4 space-y-4">
            <div>
              <input
                type="file"
                id="mold-doc-upload"
                accept=".pdf,.docx,.pptx"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) {
                    setFile(f);
                    setResult(null);
                  }
                }}
                className="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100"
              />
              {file && (file.name.endsWith('.pdf') || file.name.endsWith('.docx') || file.name.endsWith('.pptx')) && (
                <div className="mt-2 text-sm text-gray-600">
                  Selected: <span className="font-medium">{file.name}</span>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={indexIntoQdrant}
                  onChange={(e) => setIndexIntoQdrant(e.target.checked)}
                />
                Index into Qdrant
              </label>
            </div>

            <button
              type="button"
              disabled={isSubmitting || !file || !(file.name.endsWith('.pdf') || file.name.endsWith('.docx') || file.name.endsWith('.pptx'))}
              onClick={async () => {
                if (!file) return;
                setIsSubmitting(true);
                setResult(null);
                try {
                  const formData = new FormData();
                  formData.append("file", file);
                  const params = new URLSearchParams({
                    index: indexIntoQdrant ? "true" : "false",
                    run_ocr: "true",
                    collection: "mold_reference_kb",
                    domain: "mold",
                  });
                  const res = await fetch(
                    `/api/proxy/agent/admin/documents/upload?${params}`,
                    { method: "POST", body: formData }
                  );
                  let json: UploadResult;
                  try {
                    json = await res.json();
                  } catch {
                    setResult({ detail: "Failed to parse response" });
                    return;
                  }
                  if (!res.ok) {
                    setResult({ detail: json.detail || "Upload failed" });
                    return;
                  }
                  setResult(json);
                } catch (err) {
                  setResult({ detail: err instanceof Error ? err.message : "Upload failed" });
                } finally {
                  setIsSubmitting(false);
                }
              }}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white font-semibold hover:bg-emerald-700 disabled:opacity-50"
            >
              {isSubmitting ? "Processing with OCR..." : "Upload Mold Document"}
            </button>
          </div>
        </div>

        <div className="mt-6 bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-800">{t("links.title")}</h2>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
            <a
              href={`/${locale}`}
              className="px-4 py-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
            >
              <div className="font-medium text-gray-900">{t("links.home")}</div>
              <div className="text-sm text-gray-600">/{locale}</div>
            </a>

            <a
              href={agentApiBase}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
            >
              <div className="font-medium text-gray-900">{t("links.agentApi")}</div>
              <div className="text-sm text-gray-600">{agentApiBase}</div>
            </a>
          </div>
        </div>

        {result && (
          <div className="mt-6 bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800">{t("result.title")}</h2>
            <pre className="mt-3 p-4 rounded-lg bg-gray-50 text-xs overflow-auto">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
