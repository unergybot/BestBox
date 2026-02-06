"use client";

import { useState, useCallback, useRef, useEffect } from "react";

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
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const FILE_ICONS: Record<string, string> = {
  xlsx: "📊",
  xls: "📊",
  pdf: "📄",
  docx: "📝",
  pptx: "📽️",
  jpg: "🖼️",
  jpeg: "🖼️",
  png: "🖼️",
  webp: "🖼️",
};

function getFileIcon(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  return FILE_ICONS[ext] || "📎";
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

export default function DocumentsUploadPage() {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // URL Import
  const [activeTab, setActiveTab] = useState<"file" | "url">("file");
  const [importUrl, setImportUrl] = useState("");
  const [enrichEnabled, setEnrichEnabled] = useState(true);
  const [urlImporting, setUrlImporting] = useState(false);
  const [urlJobId, setUrlJobId] = useState<string | null>(null);
  const [urlJobStatus, setUrlJobStatus] = useState<Record<string, unknown> | null>(null);

  // Options
  const [collection, setCollection] = useState("mold_reference_kb");
  const [domain, setDomain] = useState("mold");
  const [ocrEngine, setOcrEngine] = useState("easyocr");
  const [forceOcr, setForceOcr] = useState(false);
  const [chunking, setChunking] = useState("auto");

  const getToken = () => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("admin_jwt_token") || localStorage.getItem("admin_token") || "";
    }
    return "";
  };

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
    [addFiles]
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) addFiles(e.target.files);
    e.target.value = "";
  };

  const uploadAll = async () => {
    const pending = files.filter((f) => f.status === "pending");
    if (!pending.length) return;

    setIsUploading(true);
    const token = getToken();

    for (const entry of pending) {
      setFiles((prev) =>
        prev.map((f) => (f.id === entry.id ? { ...f, status: "uploading", progress: 10 } : f))
      );

      try {
        const formData = new FormData();
        formData.append("file", entry.file);

        const params = new URLSearchParams({
          collection,
          domain,
          ocr_engine: ocrEngine,
          chunking,
          force_ocr: forceOcr.toString(),
        });

        setFiles((prev) =>
          prev.map((f) => (f.id === entry.id ? { ...f, status: "converting", progress: 30 } : f))
        );

        const headers: Record<string, string> = {};
        if (token) {
          if (token.includes(".")) {
            headers["Authorization"] = `Bearer ${token}`;
          } else {
            headers["admin-token"] = token;
          }
        }

        const res = await fetch(`${API_BASE}/admin/documents/upload?${params}`, {
          method: "POST",
          body: formData,
          headers,
        });

        setFiles((prev) =>
          prev.map((f) => (f.id === entry.id ? { ...f, status: "extracting", progress: 60 } : f))
        );

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Upload failed" }));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }

        const data: UploadResult = await res.json();

        setFiles((prev) =>
          prev.map((f) => (f.id === entry.id ? { ...f, status: "indexing", progress: 85 } : f))
        );

        await new Promise((r) => setTimeout(r, 300));

        setFiles((prev) =>
          prev.map((f) =>
            f.id === entry.id ? { ...f, status: "done", progress: 100, result: data } : f
          )
        );
      } catch (err) {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === entry.id
              ? { ...f, status: "error", error: err instanceof Error ? err.message : "Upload failed" }
              : f
          )
        );
      }
    }

    setIsUploading(false);
  };

  const isValidUrl = (url: string) => {
    try {
      const u = new URL(url);
      if (!["http:", "https:"].includes(u.protocol)) return false;
      const ext = u.pathname.split(".").pop()?.toLowerCase();
      return ["pdf", "docx", "pptx", "xlsx", "xls"].includes(ext || "");
    } catch {
      return false;
    }
  };

  const importFromUrl = async () => {
    if (!isValidUrl(importUrl)) return;

    setUrlImporting(true);
    setUrlJobId(null);
    setUrlJobStatus(null);

    const token = getToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) {
      if (token.includes(".")) {
        headers["Authorization"] = `Bearer ${token}`;
      } else {
        headers["admin-token"] = token;
      }
    }

    try {
      const res = await fetch(`${API_BASE}/admin/documents/upload-url`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          url: importUrl,
          collection,
          domain,
          ocr_engine: ocrEngine,
          chunking,
          enrich: enrichEnabled,
          force: forceOcr,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Import failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setUrlJobId(data.job_id);
      setUrlJobStatus({ id: data.job_id, status: data.status, filename: data.filename, stage: "queued" });
    } catch (err) {
      setUrlJobStatus({
        status: "failed",
        error: err instanceof Error ? err.message : "Import failed",
      });
      setUrlImporting(false);
    }
  };

  // Poll job status when urlJobId is set
  useEffect(() => {
    if (!urlJobId) return;

    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) {
      if (token.includes(".")) {
        headers["Authorization"] = `Bearer ${token}`;
      } else {
        headers["admin-token"] = token;
      }
    }

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/admin/documents/jobs/${urlJobId}`, { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const job = await res.json();
        setUrlJobStatus(job);

        if (job.status === "completed" || job.status === "failed") {
          clearInterval(interval);
          setUrlImporting(false);
        }
      } catch {
        clearInterval(interval);
        setUrlImporting(false);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [urlJobId]);

  const pendingCount = files.filter((f) => f.status === "pending").length;
  const doneCount = files.filter((f) => f.status === "done").length;
  const errorCount = files.filter((f) => f.status === "error").length;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Document Upload</h1>
        <p className="text-gray-600 mt-2">
          Upload documents for processing through the Docling pipeline. Supports Excel, PDF, DOCX,
          PPTX, and images.
        </p>
      </header>

      {/* Tab Selector */}
      <div className="flex bg-gray-100 rounded-lg p-1 mb-4">
        <button
          onClick={() => setActiveTab("file")}
          className={`flex-1 py-2 px-4 text-sm font-medium rounded-md transition-all ${
            activeTab === "file"
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Upload Files
        </button>
        <button
          onClick={() => setActiveTab("url")}
          className={`flex-1 py-2 px-4 text-sm font-medium rounded-md transition-all ${
            activeTab === "url"
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Import from URL
        </button>
      </div>

      {/* Drop Zone (file tab) */}
      {activeTab === "file" && (
        <div
          className={`border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer ${
            dragActive ? "border-blue-500 bg-blue-50 scale-[1.01]" : "border-gray-300 bg-white hover:border-gray-400"
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            multiple
            accept=".pdf,.docx,.pptx,.xlsx,.xls,.jpg,.jpeg,.png,.webp,.tiff,.bmp"
            onChange={handleFileInput}
          />
          <svg className="w-14 h-14 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-gray-600 font-medium">Drop files here or click to browse</p>
          <p className="text-sm text-gray-400 mt-1">
            PDF, DOCX, PPTX, XLSX, Images — max 50 MB each
          </p>
        </div>
      )}

      {/* URL Import (url tab) */}
      {activeTab === "url" && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <div className="flex gap-3">
            <input
              type="url"
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
              placeholder="https://example.com/document.pdf"
              className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              disabled={urlImporting}
            />
            <button
              onClick={importFromUrl}
              disabled={!isValidUrl(importUrl) || urlImporting}
              className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                !isValidUrl(importUrl) || urlImporting
                  ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                  : "bg-blue-600 text-white hover:bg-blue-700"
              }`}
            >
              {urlImporting ? "Importing..." : "Import"}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Supported: PDF, DOCX, PPTX, XLSX, XLS
          </p>

          <label className="flex items-center gap-2 text-sm text-gray-600 mt-4">
            <input
              type="checkbox"
              checked={enrichEnabled}
              onChange={(e) => setEnrichEnabled(e.target.checked)}
              className="rounded text-blue-600"
              disabled={urlImporting}
            />
            LLM Enrichment
          </label>

          {/* Job Status */}
          {urlJobStatus && (
            <div className="mt-5 border-t border-gray-100 pt-4">
              {urlJobStatus.status === "failed" ? (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm font-medium text-red-700">Import Failed</p>
                  <p className="text-xs text-red-600 mt-1">
                    {(urlJobStatus.error as string) || "An unknown error occurred"}
                  </p>
                </div>
              ) : urlJobStatus.status === "completed" ? (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <p className="text-sm font-medium text-green-700">Import Complete</p>
                  <div className="mt-2 grid grid-cols-3 gap-3 text-xs">
                    <div>
                      <span className="text-gray-500">Chunks:</span>{" "}
                      <span className="font-medium">{urlJobStatus.total_chunks as number ?? 0}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Enriched:</span>{" "}
                      <span className="font-medium text-green-600">{urlJobStatus.enriched_chunks as number ?? 0}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Indexed:</span>{" "}
                      <span className="font-medium text-blue-600">{urlJobStatus.total_chunks as number ?? 0}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-gray-700">
                      {(urlJobStatus.filename as string) || "Processing..."}
                    </p>
                    <span className="text-xs text-blue-500 font-medium capitalize">
                      {(urlJobStatus.stage as string) || (urlJobStatus.status as string) || "queued"}
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div
                      className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
                      style={{
                        width: `${
                          urlJobStatus.stage === "downloading" ? 15 :
                          urlJobStatus.stage === "converting" ? 35 :
                          urlJobStatus.stage === "chunking" ? 55 :
                          urlJobStatus.stage === "enriching" ? 70 + ((urlJobStatus.enrichment_progress as number) || 0) * 0.2 :
                          urlJobStatus.stage === "indexing" ? 92 :
                          10
                        }%`,
                      }}
                    />
                  </div>
                  {urlJobStatus.stage === "enriching" && (urlJobStatus.enrichment_progress as number) > 0 && (
                    <p className="text-xs text-gray-500 mt-1">
                      Enrichment: {urlJobStatus.enriched_chunks as number}/{urlJobStatus.total_chunks as number} chunks ({Math.round(urlJobStatus.enrichment_progress as number)}%)
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Processing Options */}
      <div className="mt-6 bg-white rounded-lg p-5 shadow-sm border border-gray-200">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Processing Options</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Target Collection</label>
            <select
              value={collection}
              onChange={(e) => setCollection(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="mold_reference_kb">mold_reference_kb</option>
              <option value="general_kb">general_kb</option>
              <option value="erp_docs">erp_docs</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Domain</label>
            <select
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="mold">Mold</option>
              <option value="erp">ERP</option>
              <option value="crm">CRM</option>
              <option value="it_ops">IT Ops</option>
              <option value="general">General</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">OCR Engine</label>
            <select
              value={ocrEngine}
              onChange={(e) => setOcrEngine(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="easyocr">EasyOCR</option>
              <option value="tesseract">Tesseract</option>
              <option value="rapidocr">RapidOCR</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Chunking Strategy</label>
            <select
              value={chunking}
              onChange={(e) => setChunking(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="auto">Auto (detect from file type)</option>
              <option value="case">Case-based (Excel)</option>
              <option value="hierarchical">Hierarchical (PDF/DOCX)</option>
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-gray-600 py-2">
              <input
                type="checkbox"
                checked={forceOcr}
                onChange={(e) => setForceOcr(e.target.checked)}
                className="rounded text-blue-600"
              />
              Force OCR
            </label>
          </div>
        </div>
      </div>

      {/* File List (file tab only) */}
      {activeTab === "file" && files.length > 0 && (
        <div className="mt-6 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">
              Files ({files.length})
              {doneCount > 0 && <span className="ml-2 text-green-600">{doneCount} done</span>}
              {errorCount > 0 && <span className="ml-2 text-red-600">{errorCount} failed</span>}
            </h2>
            {(doneCount > 0 || errorCount > 0) && (
              <button onClick={clearCompleted} className="text-xs text-gray-500 hover:text-gray-700">
                Clear completed
              </button>
            )}
          </div>

          {files.map((entry) => (
            <div key={entry.id} className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-2xl flex-shrink-0">{getFileIcon(entry.file.name)}</span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{entry.file.name}</p>
                    <p className="text-xs text-gray-400">{formatFileSize(entry.file.size)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs font-medium ${STATUS_LABELS[entry.status].color}`}>
                    {STATUS_LABELS[entry.status].text}
                  </span>
                  {entry.status === "pending" && (
                    <button onClick={() => removeFile(entry.id)} className="text-gray-400 hover:text-red-500">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>

              {entry.status !== "pending" && entry.status !== "done" && entry.status !== "error" && (
                <div className="mt-3 w-full bg-gray-100 rounded-full h-1.5">
                  <div
                    className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${entry.progress}%` }}
                  />
                </div>
              )}

              {entry.result && (
                <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <span className="text-gray-500">Chunks:</span>{" "}
                    <span className="font-medium">{entry.result.chunks_extracted}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Indexed:</span>{" "}
                    <span className="font-medium text-green-600">{entry.result.chunks_indexed}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Method:</span>{" "}
                    <span className="font-medium">{entry.result.processing_method}</span>
                  </div>
                </div>
              )}

              {entry.error && <p className="mt-2 text-xs text-red-600">{entry.error}</p>}
            </div>
          ))}
        </div>
      )}

      {/* Upload Button (file tab only) */}
      {activeTab === "file" && (
        <div className="mt-6">
          <button
            onClick={uploadAll}
            disabled={pendingCount === 0 || isUploading}
            className={`w-full py-3 rounded-lg font-medium transition-colors ${
              pendingCount === 0 || isUploading
                ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {isUploading
              ? "Processing..."
              : pendingCount > 0
              ? `Upload ${pendingCount} file${pendingCount > 1 ? "s" : ""}`
              : "Add files to upload"}
          </button>
        </div>
      )}
    </div>
  );
}
