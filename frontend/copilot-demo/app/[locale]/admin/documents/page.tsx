"use client";

import { useState, useCallback, useRef } from "react";
import { useTranslations } from "next-intl";

interface FileEntry {
  id: string;
  file: File;
  status: "pending" | "uploading" | "converting" | "extracting" | "indexing" | "done" | "error";
  progress: number;
  result?: UploadResult;
  error?: string;
}

interface UploadResult {
  status: string;
  filename: string;
  file_type: string;
  chunks_extracted: number;
  chunks_indexed: number;
  collection: string;
  domain: string;
  processing_method: string;
  layout_detected?: {
    tables: number;
    images: number;
    headers: number;
  };
  processing_time?: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("admin_jwt_token") || localStorage.getItem("admin_token") || "";
  if (!token) return {};
  if (token.includes(".")) return { Authorization: `Bearer ${token}` };
  return { "admin-token": token };
}

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  pending: { text: "Pending", color: "text-gray-500" },
  uploading: { text: "Uploading…", color: "text-blue-500" },
  converting: { text: "Converting…", color: "text-blue-500" },
  extracting: { text: "Extracting…", color: "text-purple-500" },
  indexing: { text: "Indexing…", color: "text-orange-500" },
  done: { text: "Done ✓", color: "text-green-600" },
  error: { text: "Failed ✗", color: "text-red-600" },
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentsPage() {
  const t = useTranslations("AdminNew.documents");

  const [files, setFiles] = useState<FileEntry[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // URL Import
  const [activeTab, setActiveTab] = useState<"file" | "url">("file");
  const [importUrl, setImportUrl] = useState("");
  const [urlImporting, setUrlImporting] = useState(false);

  // Options
  const [collection, setCollection] = useState("mold_reference_kb");
  const [domain, setDomain] = useState("mold");
  const [ocrEngine, setOcrEngine] = useState("easyocr");
  const [chunking, setChunking] = useState("auto");
  const [enrichEnabled, setEnrichEnabled] = useState(true);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const entries: FileEntry[] = Array.from(newFiles).map((file) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      file,
      status: "pending" as const,
      progress: 0,
    }));
    setFiles((prev) => [...prev, ...entries]);
  }, []);

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const clearCompleted = () => {
    setFiles((prev) => prev.filter((f) => f.status !== "done" && f.status !== "error"));
  };

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
    },
    [addFiles],
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) addFiles(e.target.files);
    e.target.value = "";
  };

  const uploadAll = async () => {
    const pending = files.filter((f) => f.status === "pending");
    if (!pending.length) return;

    setIsUploading(true);
    const headers = getAuthHeaders();

    for (const entry of pending) {
      setFiles((prev) =>
        prev.map((f) => (f.id === entry.id ? { ...f, status: "uploading", progress: 10 } : f)),
      );

      try {
        const formData = new FormData();
        formData.append("file", entry.file);

        const params = new URLSearchParams({
          collection,
          domain,
          ocr_engine: ocrEngine,
          chunking,
        });

        setFiles((prev) =>
          prev.map((f) => (f.id === entry.id ? { ...f, status: "converting", progress: 30 } : f)),
        );

        const res = await fetch(`${API_BASE}/admin/documents/upload?${params}`, {
          method: "POST",
          body: formData,
          headers,
        });

        setFiles((prev) =>
          prev.map((f) => (f.id === entry.id ? { ...f, status: "extracting", progress: 60 } : f)),
        );

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Upload failed" }));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }

        const data: UploadResult = await res.json();

        setFiles((prev) =>
          prev.map((f) => (f.id === entry.id ? { ...f, status: "indexing", progress: 85 } : f)),
        );

        await new Promise((r) => setTimeout(r, 300));

        setFiles((prev) =>
          prev.map((f) =>
            f.id === entry.id ? { ...f, status: "done", progress: 100, result: data } : f,
          ),
        );
      } catch (err) {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === entry.id
              ? { ...f, status: "error", error: err instanceof Error ? err.message : "Upload failed" }
              : f,
          ),
        );
      }
    }
    setIsUploading(false);
  };

  const handleUrlImport = async () => {
    if (!importUrl) return;
    setUrlImporting(true);
    try {
      const res = await fetch(`${API_BASE}/admin/documents/upload-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({
          url: importUrl,
          collection,
          domain,
          ocr_engine: ocrEngine,
          chunking,
          enrich: enrichEnabled,
        }),
      });
      if (res.ok) {
        setImportUrl("");
      }
    } catch (err) {
      console.error("URL import error:", err);
    }
    setUrlImporting(false);
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t("title")}</h1>
        <p className="text-sm text-gray-500 mt-1">{t("subtitle")}</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 mb-6">
        <button
          onClick={() => setActiveTab("file")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "file" ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-gray-100"
          }`}
        >
          {t("tabs.upload")}
        </button>
        <button
          onClick={() => setActiveTab("url")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "url" ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-gray-100"
          }`}
        >
          {t("tabs.urlImport")}
        </button>
      </div>

      {activeTab === "file" && (
        <div className="space-y-6">
          {/* Dropzone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              dragActive
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 hover:border-gray-400 bg-white"
            }`}
          >
            <svg className="w-12 h-12 mx-auto text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-gray-600">{t("upload.dropzone")}</p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.pptx,.xlsx,.xls,.jpg,.jpeg,.png,.webp,.tiff,.bmp"
              onChange={handleFileInput}
              className="hidden"
            />
          </div>

          {/* Options */}
          <div className="bg-white rounded-lg shadow-sm p-4 grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("upload.collection")}</label>
              <input
                value={collection}
                onChange={(e) => setCollection(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("upload.domain")}</label>
              <input
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("upload.ocrEngine")}</label>
              <select
                value={ocrEngine}
                onChange={(e) => setOcrEngine(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm"
              >
                <option value="easyocr">EasyOCR</option>
                <option value="tesseract">Tesseract</option>
                <option value="rapidocr">RapidOCR</option>
                <option value="glm-ocr">GLM-OCR (GPU + Layout)</option>
              </select>
              {ocrEngine === "glm-ocr" && (
                <p className="mt-1 text-xs text-blue-600">{t("upload.glmOcrHint")}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t("upload.chunking")}</label>
              <select
                value={chunking}
                onChange={(e) => setChunking(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm"
              >
                <option value="auto">Auto</option>
                <option value="case">Case</option>
                <option value="hierarchical">Hierarchical</option>
              </select>
            </div>
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm">
              <div className="p-4 border-b flex items-center justify-between">
                <span className="text-sm font-medium">{files.length} {t("upload.selected")}</span>
                <div className="flex gap-2">
                  <button onClick={clearCompleted} className="text-sm text-gray-500 hover:text-gray-700">Clear completed</button>
                  <button
                    onClick={uploadAll}
                    disabled={isUploading || !files.some((f) => f.status === "pending")}
                    className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                  >
                    {isUploading ? t("upload.processing") : t("upload.button")}
                  </button>
                </div>
              </div>
              <div className="divide-y">
                {files.map((entry) => (
                  <div key={entry.id} className="p-4">
                    <div className="flex items-center gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">{entry.file.name}</div>
                        <div className="text-xs text-gray-500">{formatFileSize(entry.file.size)}</div>
                      </div>
                      <div className={`text-xs font-medium ${STATUS_LABELS[entry.status]?.color}`}>
                        {STATUS_LABELS[entry.status]?.text}
                      </div>
                      {entry.status === "pending" && (
                        <button onClick={() => removeFile(entry.id)} className="text-gray-400 hover:text-red-500">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                      {entry.status !== "pending" && entry.status !== "done" && entry.status !== "error" && (
                        <div className="w-16">
                          <div className="bg-gray-200 rounded-full h-1.5">
                            <div
                              className="bg-blue-500 h-1.5 rounded-full transition-all"
                              style={{ width: `${entry.progress}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                    {entry.status === "done" && entry.result?.layout_detected && (
                      <div className="mt-2 rounded bg-blue-50 px-3 py-2 text-xs text-blue-800">
                        <div className="font-medium">{t("upload.layout.title")}</div>
                        <div className="mt-1 flex flex-wrap gap-3 text-blue-700">
                          <span>
                            {t("upload.layout.tables")}: {entry.result.layout_detected.tables}
                          </span>
                          <span>
                            {t("upload.layout.images")}: {entry.result.layout_detected.images}
                          </span>
                          <span>
                            {t("upload.layout.headers")}: {entry.result.layout_detected.headers}
                          </span>
                          {typeof entry.result.processing_time === "number" && (
                            <span>
                              {t("upload.layout.processingTime")}: {entry.result.processing_time.toFixed(1)}s
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                    {entry.status === "error" && entry.error && (
                      <div className="mt-2 rounded bg-red-50 px-3 py-2 text-xs text-red-800">
                        <div className="font-medium">Error</div>
                        <div className="mt-1 text-red-700">{entry.error}</div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === "url" && (
        <div className="bg-white rounded-lg shadow-sm p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("urlImport.urlLabel")}</label>
            <input
              type="url"
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
              placeholder={t("urlImport.urlPlaceholder")}
              className="w-full px-4 py-2 border rounded-lg text-sm"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={enrichEnabled}
              onChange={(e) => setEnrichEnabled(e.target.checked)}
            />
            {t("upload.options.enrichWithLLM")}
          </label>
          <button
            onClick={handleUrlImport}
            disabled={urlImporting || !importUrl}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {urlImporting ? t("urlImport.importing") : t("urlImport.button")}
          </button>
        </div>
      )}
    </div>
  );
}
