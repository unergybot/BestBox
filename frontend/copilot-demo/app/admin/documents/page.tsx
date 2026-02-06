"use client";

import { useState, useCallback } from "react";

interface UploadResult {
    status: string;
    filename: string;
    file_type: string;
    title: string;
    text_length: number;
    image_count: number;
    ocr_count: number;
    indexed: boolean;
    collection: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8002";

export default function DocumentsUploadPage() {
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [result, setResult] = useState<UploadResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [dragActive, setDragActive] = useState(false);

    // Options
    const [runOcr, setRunOcr] = useState(true);
    const [indexDoc, setIndexDoc] = useState(true);
    const [collection] = useState("mold_reference_kb");

    const handleDrag = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setFile(e.dataTransfer.files[0]);
            setResult(null);
            setError(null);
        }
    }, []);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setResult(null);
            setError(null);
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        setUploading(true);
        setError(null);
        setResult(null);

        try {
            const formData = new FormData();
            formData.append("file", file);

            const params = new URLSearchParams({
                index: indexDoc.toString(),
                collection: collection,
                run_ocr: runOcr.toString(),
                domain: "mold",
            });

            const res = await fetch(`${API_BASE}/admin/documents/upload?${params}`, {
                method: "POST",
                body: formData,
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Upload failed");
            }

            const data = await res.json();
            setResult(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Upload failed");
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-2xl mx-auto">
                <header className="mb-8">
                    <h1 className="text-3xl font-bold text-gray-900">
                        Mold Knowledge Base Upload
                    </h1>
                    <p className="text-gray-600 mt-2">
                        Upload PDF, DOCX, or PPTX documents. Images will be processed with
                        OCR.
                    </p>
                </header>

                {/* Upload Zone */}
                <div
                    className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${dragActive
                            ? "border-blue-500 bg-blue-50"
                            : "border-gray-300 bg-white"
                        }`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                >
                    <input
                        type="file"
                        id="file-upload"
                        className="hidden"
                        accept=".pdf,.docx,.pptx"
                        onChange={handleFileChange}
                    />
                    <label
                        htmlFor="file-upload"
                        className="cursor-pointer flex flex-col items-center"
                    >
                        <svg
                            className="w-12 h-12 text-gray-400 mb-4"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                            />
                        </svg>
                        <span className="text-gray-600">
                            {file ? file.name : "Drop files here or click to upload"}
                        </span>
                        <span className="text-sm text-gray-400 mt-1">
                            PDF, DOCX, PPTX (max 50MB)
                        </span>
                    </label>
                </div>

                {/* Options */}
                <div className="mt-6 bg-white rounded-lg p-4 shadow-sm">
                    <h2 className="text-sm font-medium text-gray-700 mb-3">Options</h2>
                    <div className="flex flex-wrap gap-4">
                        <label className="flex items-center gap-2 text-sm text-gray-600">
                            <input
                                type="checkbox"
                                checked={runOcr}
                                onChange={(e) => setRunOcr(e.target.checked)}
                                className="rounded text-blue-600"
                            />
                            Run OCR on images
                        </label>
                        <label className="flex items-center gap-2 text-sm text-gray-600">
                            <input
                                type="checkbox"
                                checked={indexDoc}
                                onChange={(e) => setIndexDoc(e.target.checked)}
                                className="rounded text-blue-600"
                            />
                            Index into Qdrant
                        </label>
                    </div>
                </div>

                {/* Upload Button */}
                <button
                    onClick={handleUpload}
                    disabled={!file || uploading}
                    className={`mt-6 w-full py-3 rounded-lg font-medium transition-colors ${!file || uploading
                            ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                            : "bg-blue-600 text-white hover:bg-blue-700"
                        }`}
                >
                    {uploading ? "Uploading & Processing..." : "Upload Document"}
                </button>

                {/* Error */}
                {error && (
                    <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                        {error}
                    </div>
                )}

                {/* Result */}
                {result && (
                    <div className="mt-6 bg-white rounded-lg p-6 shadow-sm">
                        <h2 className="text-lg font-semibold text-green-700 mb-4">
                            ✓ Upload Successful
                        </h2>
                        <dl className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <dt className="text-gray-500">Filename</dt>
                                <dd className="font-medium">{result.filename}</dd>
                            </div>
                            <div>
                                <dt className="text-gray-500">Title</dt>
                                <dd className="font-medium">{result.title}</dd>
                            </div>
                            <div>
                                <dt className="text-gray-500">File Type</dt>
                                <dd className="font-medium uppercase">{result.file_type}</dd>
                            </div>
                            <div>
                                <dt className="text-gray-500">Text Length</dt>
                                <dd className="font-medium">
                                    {result.text_length.toLocaleString()} chars
                                </dd>
                            </div>
                            <div>
                                <dt className="text-gray-500">Images Found</dt>
                                <dd className="font-medium">{result.image_count}</dd>
                            </div>
                            <div>
                                <dt className="text-gray-500">OCR Results</dt>
                                <dd className="font-medium">{result.ocr_count}</dd>
                            </div>
                            <div>
                                <dt className="text-gray-500">Indexed</dt>
                                <dd className="font-medium">
                                    {result.indexed ? (
                                        <span className="text-green-600">Yes</span>
                                    ) : (
                                        <span className="text-gray-500">No</span>
                                    )}
                                </dd>
                            </div>
                            {result.collection && (
                                <div>
                                    <dt className="text-gray-500">Collection</dt>
                                    <dd className="font-medium">{result.collection}</dd>
                                </div>
                            )}
                        </dl>
                    </div>
                )}

                {/* Back Link */}
                <div className="mt-8 text-center">
                    <a
                        href="/admin"
                        className="text-blue-600 hover:text-blue-800 text-sm"
                    >
                        ← Back to Admin
                    </a>
                </div>
            </div>
        </div>
    );
}
