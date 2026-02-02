
import React, { useRef, useState } from 'react';

interface FileUploadButtonProps {
    onFileSelect: (filePath: string, fileName: string) => void;
    disabled?: boolean;
}

export const FileUploadButton: React.FC<FileUploadButtonProps> = ({
    onFileSelect,
    disabled = false
}) => {
    const [isUploading, setIsUploading] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        try {
            setIsUploading(true);
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Upload failed');
            }

            const data = await response.json();
            if (data.success) {
                onFileSelect(data.filepath, data.filename);
            }
        } catch (error) {
            console.error('Upload error:', error);
            // Ideally show a toast/error here
        } finally {
            setIsUploading(false);
            // Reset input so same file can be selected again
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    };

    return (
        <>
            <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                className="hidden"
                accept="image/*,application/pdf,.xlsx,.xls"
            />
            <button
                onClick={handleClick}
                disabled={disabled || isUploading}
                className={`
          flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all mb-1 mr-1
          ${disabled || isUploading
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        : 'text-gray-500 hover:bg-gray-100 hover:text-blue-600'}
        `}
                title="Upload File"
            >
                {isUploading ? (
                    <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                ) : (
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="w-5 h-5"
                    >
                        <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                    </svg>
                )}
            </button>
        </>
    );
};
