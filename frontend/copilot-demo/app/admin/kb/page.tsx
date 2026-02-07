"use client";

import { useEffect, useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface Collection {
  name: string;
  points_count: number;
  vectors_count: number;
  status: string;
}

interface Document {
  doc_id: string;
  source_file: string;
  file_type: string;
  domain: string;
  upload_date: string;
  uploaded_by: string;
  chunk_count: number;
  has_images: boolean;
}

interface SearchResult {
  score: number;
  doc_id: string;
  source_file: string;
  text: string;
  defect_type: string;
  mold_id: string;
  domain: string;
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("admin_jwt_token") || localStorage.getItem("admin_token") || "";
  if (!token) return {};
  if (token.includes(".")) return { Authorization: `Bearer ${token}` };
  return { "admin-token": token };
}

function ImageThumb({ imageId, onClick }: { imageId: string; onClick: () => void }) {
  const [src, setSrc] = useState<string>("");

  useEffect(() => {
    let revoke = "";
    fetch(`${API_BASE}/admin/kb/images/${imageId}`, { headers: getAuthHeaders() })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        setSrc(url);
        revoke = url;
      })
      .catch(() => {});
    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [imageId]);

  if (!src) return <div className="w-20 h-20 rounded-lg bg-gray-100 animate-pulse" />;

  return (
    <button
      onClick={onClick}
      className="w-20 h-20 rounded-lg overflow-hidden border border-gray-200 hover:border-blue-400 transition-colors flex-shrink-0"
    >
      <img src={src} alt={imageId} className="w-full h-full object-cover" />
    </button>
  );
}

function ImageFull({ imageId }: { imageId: string }) {
  const [src, setSrc] = useState<string>("");

  useEffect(() => {
    let revoke = "";
    fetch(`${API_BASE}/admin/kb/images/${imageId}`, { headers: getAuthHeaders() })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        setSrc(url);
        revoke = url;
      })
      .catch(() => {});
    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [imageId]);

  if (!src) return <div className="w-64 h-64 bg-gray-800 animate-pulse rounded" />;

  return <img src={src} alt={imageId} className="max-w-full max-h-[80vh] rounded-lg shadow-2xl" />;
}

function InlineImage({ imageId, onClick }: { imageId: string; onClick: () => void }) {
  const [src, setSrc] = useState<string>("");

  useEffect(() => {
    let revoke = "";
    fetch(`${API_BASE}/admin/kb/images/${imageId}`, { headers: getAuthHeaders() })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        setSrc(url);
        revoke = url;
      })
      .catch(() => {});
    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [imageId]);

  if (!src) return <div className="w-full h-32 rounded-lg bg-gray-100 animate-pulse my-2" />;

  return (
    <button
      onClick={onClick}
      className="block w-full my-3 rounded-lg overflow-hidden border border-gray-200 hover:border-blue-400 transition-colors"
    >
      <img src={src} alt={imageId} className="w-full h-auto max-h-64 object-contain bg-gray-50" />
    </button>
  );
}

function ChunkContent({ text, imageIds, onImageClick }: { text: string; imageIds: string[]; onImageClick: (id: string) => void }) {
  const placeholder = "<!-- image -->";
  const parts = text.split(placeholder);

  if (parts.length === 1 || imageIds.length === 0) {
    return <p className="text-gray-800 whitespace-pre-wrap">{text}</p>;
  }

  return (
    <div className="text-gray-800">
      {parts.map((part, index) => (
        <span key={index}>
          {part && <span className="whitespace-pre-wrap">{part}</span>}
          {index < parts.length - 1 && index < imageIds.length && (
            <InlineImage
              imageId={imageIds[index]}
              onClick={() => onImageClick(imageIds[index])}
            />
          )}
        </span>
      ))}
    </div>
  );
}

export default function KBDashboardPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedCollection, setSelectedCollection] = useState("mold_reference_kb");
  const [loading, setLoading] = useState(false);
  const [domainFilter, setDomainFilter] = useState("");
  const [fileTypeFilter, setFileTypeFilter] = useState("");

  // Search test
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // Bulk selection
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());

  // Detail view
  const [detailDoc, setDetailDoc] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<Record<string, unknown> | null>(null);

  // Lightbox
  const [lightboxImage, setLightboxImage] = useState<string | null>(null);

  const fetchCollections = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/kb/collections`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) setCollections(await res.json());
    } catch (e) {
      console.error("Failed to fetch collections:", e);
    }
  }, []);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ collection: selectedCollection, limit: "50" });
      if (domainFilter) params.set("domain", domainFilter);
      if (fileTypeFilter) params.set("file_type", fileTypeFilter);

      const res = await fetch(`${API_BASE}/admin/kb/documents?${params}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch (e) {
      console.error("Failed to fetch documents:", e);
    } finally {
      setLoading(false);
    }
  }, [selectedCollection, domainFilter, fileTypeFilter]);

  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await fetch(`${API_BASE}/admin/kb/search-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ query: searchQuery, collection: selectedCollection, limit: 5 }),
      });
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
      }
    } catch (e) {
      console.error("Search failed:", e);
    } finally {
      setSearching(false);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedDocs.size === 0) return;
    if (!confirm(`Delete ${selectedDocs.size} document(s)? This cannot be undone.`)) return;

    try {
      const res = await fetch(`${API_BASE}/admin/kb/documents/bulk`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ doc_ids: Array.from(selectedDocs), collection: selectedCollection }),
      });
      if (res.ok) {
        setSelectedDocs(new Set());
        fetchDocuments();
        fetchCollections();
      }
    } catch (e) {
      console.error("Bulk delete failed:", e);
    }
  };

  const openDetail = async (docId: string) => {
    setDetailDoc(docId);
    try {
      const res = await fetch(
        `${API_BASE}/admin/kb/documents/${docId}?collection=${selectedCollection}`,
        { headers: getAuthHeaders() }
      );
      if (res.ok) setDetailData(await res.json());
    } catch (e) {
      console.error("Failed to load document:", e);
    }
  };

  const toggleDocSelection = (docId: string) => {
    setSelectedDocs((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  };

  return (
    <div className="p-6">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Knowledge Base</h1>
        <p className="text-gray-600 mt-1">Browse, search, and manage indexed documents</p>
      </header>

      {/* Collection overview cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-8">
        {collections.map((col) => (
          <button
            key={col.name}
            onClick={() => setSelectedCollection(col.name)}
            className={`p-4 rounded-lg border text-left transition-all ${
              selectedCollection === col.name
                ? "border-blue-500 bg-blue-50 ring-1 ring-blue-200"
                : "border-gray-200 bg-white hover:border-gray-300"
            }`}
          >
            <h3 className="text-sm font-semibold text-gray-900 truncate">{col.name}</h3>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-gray-900">
                {col.points_count.toLocaleString()}
              </span>
              <span className="text-xs text-gray-500">points</span>
            </div>
            <div className="mt-1 text-xs text-gray-400">
              {col.vectors_count.toLocaleString()} vectors · {col.status}
            </div>
          </button>
        ))}
        {collections.length === 0 && (
          <div className="col-span-full text-center py-8 text-gray-400">
            No collections found. Upload documents to get started.
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-2 text-sm"
        >
          <option value="">All domains</option>
          <option value="mold">Mold</option>
          <option value="erp">ERP</option>
          <option value="crm">CRM</option>
          <option value="it_ops">IT Ops</option>
        </select>
        <select
          value={fileTypeFilter}
          onChange={(e) => setFileTypeFilter(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-2 text-sm"
        >
          <option value="">All file types</option>
          <option value="xlsx">Excel</option>
          <option value="pdf">PDF</option>
          <option value="docx">DOCX</option>
          <option value="pptx">PPTX</option>
        </select>
        {selectedDocs.size > 0 && (
          <button
            onClick={handleBulkDelete}
            className="ml-auto px-4 py-2 bg-red-600 text-white text-sm rounded-md hover:bg-red-700 transition-colors"
          >
            Delete {selectedDocs.size} selected
          </button>
        )}
      </div>

      {/* Document table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left w-8">
                <input
                  type="checkbox"
                  onChange={(e) => {
                    if (e.target.checked) setSelectedDocs(new Set(documents.map((d) => d.doc_id)));
                    else setSelectedDocs(new Set());
                  }}
                  checked={selectedDocs.size === documents.length && documents.length > 0}
                  className="rounded"
                />
              </th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Filename</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Type</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Domain</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Chunks</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Uploaded</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  Loading…
                </td>
              </tr>
            ) : documents.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  No documents found in this collection.
                </td>
              </tr>
            ) : (
              documents.map((doc) => (
                <tr key={doc.doc_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selectedDocs.has(doc.doc_id)}
                      onChange={() => toggleDocSelection(doc.doc_id)}
                      className="rounded"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => openDetail(doc.doc_id)}
                      className="text-blue-600 hover:underline font-medium truncate max-w-[200px] block"
                    >
                      {doc.source_file}
                    </button>
                  </td>
                  <td className="px-4 py-3 uppercase text-xs text-gray-500">{doc.file_type}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                      {doc.domain}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{doc.chunk_count}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {doc.upload_date ? new Date(doc.upload_date).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => openDetail(doc.doc_id)}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Search test panel */}
      <div className="mt-8 bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Search Test</h2>
        <p className="text-sm text-gray-500 mb-4">
          Type a query to test how documents rank in retrieval.
        </p>
        <div className="flex gap-3">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="e.g. burr defect on mold M-2024-001"
            className="flex-1 border border-gray-300 rounded-md px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSearch}
            disabled={searching || !searchQuery.trim()}
            className="px-6 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {searching ? "Searching…" : "Search"}
          </button>
        </div>

        {searchResults.length > 0 && (
          <div className="mt-4 space-y-3">
            {searchResults.map((r, idx) => (
              <div key={idx} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono text-gray-500">
                    Score: {r.score.toFixed(4)}
                  </span>
                  <span className="text-xs text-gray-400">{r.source_file}</span>
                </div>
                <p className="text-sm text-gray-800 line-clamp-3">{r.text}</p>
                <div className="mt-2 flex gap-2 text-xs">
                  {r.defect_type && (
                    <span className="px-2 py-0.5 bg-red-50 text-red-600 rounded">
                      {r.defect_type}
                    </span>
                  )}
                  {r.mold_id && (
                    <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded">
                      {r.mold_id}
                    </span>
                  )}
                  {r.domain && (
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                      {r.domain}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Document detail modal */}
      {detailDoc && detailData && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-6">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[80vh] overflow-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  {(detailData as Record<string, unknown>).source_file as string || "Document Detail"}
                </h2>
                <p className="text-xs text-gray-400">
                  {(detailData as Record<string, unknown>).total_chunks as number || 0} chunks · {(detailData as Record<string, unknown>).processing_method as string || "unknown"}
                </p>
              </div>
              <button
                onClick={() => { setDetailDoc(null); setDetailData(null); }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 space-y-4">
              {/* Metadata */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Domain:</span>{" "}
                  <span className="font-medium">{(detailData as Record<string, unknown>).domain as string}</span>
                </div>
                <div>
                  <span className="text-gray-500">File type:</span>{" "}
                  <span className="font-medium uppercase">{(detailData as Record<string, unknown>).file_type as string}</span>
                </div>
                <div>
                  <span className="text-gray-500">Uploaded by:</span>{" "}
                  <span className="font-medium">{(detailData as Record<string, unknown>).uploaded_by as string || "—"}</span>
                </div>
                <div>
                  <span className="text-gray-500">Upload date:</span>{" "}
                  <span className="font-medium">
                    {(detailData as Record<string, unknown>).upload_date
                      ? new Date((detailData as Record<string, unknown>).upload_date as string).toLocaleString()
                      : "—"}
                  </span>
                </div>
                {(detailData as Record<string, unknown>).source_url ? (
                  <div className="col-span-2">
                    <span className="text-gray-500">Source URL:</span>{" "}
                    <a
                      href={(detailData as Record<string, unknown>).source_url as string}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-blue-600 hover:underline truncate inline-block max-w-md"
                    >
                      {(detailData as Record<string, unknown>).source_url as string}
                    </a>
                  </div>
                ) : null}
                {(() => {
                  const chunks = (detailData as Record<string, unknown>).chunks as Array<Record<string, unknown>> || [];
                  const totalImages = chunks.reduce((sum: number, c: Record<string, unknown>) =>
                    sum + ((c.image_ids as string[] || []).length), 0);
                  return totalImages > 0 ? (
                    <div>
                      <span className="text-gray-500">Images:</span>{" "}
                      <span className="font-medium">{totalImages}</span>
                    </div>
                  ) : null;
                })()}
              </div>

              {/* Chunks */}
              <h3 className="text-sm font-semibold text-gray-700 mt-4">Chunks</h3>
              <div className="space-y-2 max-h-96 overflow-auto">
                {((detailData as Record<string, unknown>).chunks as Array<Record<string, unknown>> || []).map(
                  (chunk: Record<string, unknown>, idx: number) => (
                    <div key={idx} className="border border-gray-200 rounded-lg p-3 text-sm">
                      <div className="flex items-center gap-2 mb-1 text-xs text-gray-400">
                        <span>Chunk #{(chunk.chunk_index as number) ?? idx}</span>
                        {chunk.defect_type ? (
                          <span className="px-1.5 py-0.5 bg-red-50 text-red-600 rounded">
                            {String(chunk.defect_type)}
                          </span>
                        ) : null}
                        {chunk.mold_id ? (
                          <span className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">
                            {String(chunk.mold_id)}
                          </span>
                        ) : null}
                        {chunk.severity ? (
                          <span className="px-1.5 py-0.5 bg-yellow-50 text-yellow-700 rounded">
                            {String(chunk.severity)}
                          </span>
                        ) : null}
                        {chunk.chunk_type === "enriched" ? (
                          <span className="px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded">
                            AI enriched
                          </span>
                        ) : null}
                        {chunk.root_cause_category ? (
                          <span className="px-1.5 py-0.5 bg-green-50 text-green-600 rounded">
                            {String(chunk.root_cause_category)}
                          </span>
                        ) : null}
                      </div>
                      <ChunkContent
                        text={chunk.text as string}
                        imageIds={(chunk.image_ids as string[]) || []}
                        onImageClick={setLightboxImage}
                      />
                    </div>
                  )
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Image lightbox */}
      {lightboxImage && (
        <div
          className="fixed inset-0 bg-black/80 z-[60] flex items-center justify-center p-8"
          onClick={() => setLightboxImage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setLightboxImage(null)}
              className="absolute -top-10 right-0 text-white hover:text-gray-300"
            >
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <ImageFull imageId={lightboxImage} />
          </div>
        </div>
      )}
    </div>
  );
}
