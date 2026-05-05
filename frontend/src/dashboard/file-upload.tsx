'use client';

import { useState, useRef, useCallback } from 'react';
import { Upload, X, File, CheckCircle, Clock, AlertCircle, FileSpreadsheet, Eye } from 'lucide-react';

type CsvTable = {
  headers: string[];
  rows: Array<Record<string, string>>;
};

interface UploadedFile {
  id: string;
  name: string;
  size: string;
  extension: string;
  status: 'processing' | 'completed' | 'error';
  progress: number;
  errorMessage?: string;
  rowsProcessed?: number;
  vectorsStored?: number;
  embeddingStatus?: string;
  csvPreview?: CsvTable;
  pdfUrl?: string;
}

const ACCEPTED_FORMATS = '.csv,.xlsx,.xls,.json,.pdf,.md,.txt,.docx';
const ACCEPTED_EXTENSIONS = new Set(['.csv', '.xlsx', '.xls', '.json', '.pdf', '.md', '.txt', '.docx']);

const MAX_FILE_SIZE_MB = 50;

function getFileExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.');
  return lastDot >= 0 ? filename.slice(lastDot).toLowerCase() : '';
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function parseCsv(text: string): CsvTable {
  const normalized = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const lines = normalized.split('\n').filter((line, index) => index === 0 || line.trim().length > 0);

  const parseLine = (line: string): string[] => {
    const cells: string[] = [];
    let current = '';
    let insideQuotes = false;

    for (let index = 0; index < line.length; index += 1) {
      const char = line[index];
      const nextChar = line[index + 1];

      if (char === '"') {
        if (insideQuotes && nextChar === '"') {
          current += '"';
          index += 1;
        } else {
          insideQuotes = !insideQuotes;
        }
      } else if (char === ',' && !insideQuotes) {
        cells.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }

    cells.push(current.trim());
    return cells;
  };

  if (lines.length === 0) {
    return { headers: [], rows: [] };
  }

  const headers = parseLine(lines[0]).map((header, index) => header || `Column ${index + 1}`);
  const rows = lines.slice(1).map((line) => {
    const values = parseLine(line);
    return headers.reduce<Record<string, string>>((accumulator, header, index) => {
      accumulator[header] = values[index] ?? '';
      return accumulator;
    }, {});
  });

  return { headers, rows };
}

async function readFileAsText(file: File): Promise<string> {
  return await file.text();
}

export function FileUpload() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only deactivate if leaving the drop zone (not entering a child)
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDragActive(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      addFiles(droppedFiles);
    }
  }, []);

  const handleZoneClick = () => {
    fileInputRef.current?.click();
  };

  const validateFile = (file: File): string | null => {
    const ext = getFileExtension(file.name);
    if (!ACCEPTED_EXTENSIONS.has(ext)) {
      return `Unsupported format "${ext}". Use CSV, Excel (.xlsx/.xls), or JSON.`;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      return `File exceeds ${MAX_FILE_SIZE_MB}MB limit.`;
    }
    return null;
  };

  const addFiles = (newFiles: File[]) => {
    const uploadEntries: UploadedFile[] = [];

    for (const file of newFiles) {
      const fileId = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const validationError = validateFile(file);
      const extension = getFileExtension(file.name);

      if (validationError) {
        uploadEntries.push({
          id: fileId,
          name: file.name,
          size: formatFileSize(file.size),
          extension,
          status: 'error',
          progress: 0,
          errorMessage: validationError,
        });
        continue;
      }

      const entry: UploadedFile = {
        id: fileId,
        name: file.name,
        size: formatFileSize(file.size),
        extension,
        status: 'processing',
        progress: 0,
      };

      uploadEntries.push(entry);

      void (async () => {
        const previewUpdates: Partial<UploadedFile> = {};

        if (extension === '.csv') {
          try {
            const csvText = await readFileAsText(file);
            previewUpdates.csvPreview = parseCsv(csvText);
          } catch (error) {
            previewUpdates.errorMessage = error instanceof Error ? error.message : 'Failed to parse CSV preview';
          }
        }

        if (extension === '.pdf') {
          previewUpdates.pdfUrl = URL.createObjectURL(file);
        }

        if (Object.keys(previewUpdates).length > 0) {
          setFiles((prev) =>
            prev.map((item) => (item.id === fileId ? { ...item, ...previewUpdates } : item))
          );
        }
      })();

      // Start upload in background
      uploadFileToBackend(file, fileId);
    }

    setFiles((prev) => [...prev, ...uploadEntries]);
  };

  const uploadFileToBackend = async (file: File, fileId: string) => {
    let progressInterval: ReturnType<typeof setInterval> | null = null;

    try {
      const formData = new FormData();
      formData.append('file', file);

      const apiUrl = '/api/upload';


      // Simulated progress while waiting for server response
      let simulatedProgress = 0;
      progressInterval = setInterval(() => {
        simulatedProgress += Math.random() * 15 + 5;
        if (simulatedProgress > 85) simulatedProgress = 85;
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId ? { ...f, progress: Math.round(simulatedProgress) } : f
          )
        );
      }, 400);

      const response = await fetch(apiUrl, {
        method: 'POST',
        body: formData,
      });

      if (progressInterval) clearInterval(progressInterval);

      if (response.ok) {
        const result = await response.json();
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId
              ? {
                  ...f,
                  status: 'completed',
                  progress: 100,
                  rowsProcessed: result.rows_processed,
                  vectorsStored: result.vectors_upserted ?? 0,
                  embeddingStatus:
                    (result.vectors_upserted ?? 0) > 0
                      ? 'Embeddings stored in Pinecone'
                      : 'Embeddings not stored (Pinecone unavailable)',
                }
              : f
          )
        );
      } else {
        let errorMsg = `Upload failed (${response.status})`;
        try {
          const errorResult = await response.json();
          errorMsg = errorResult.message || errorMsg;
        } catch {
          // Response wasn't JSON
        }
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId
              ? { ...f, status: 'error', progress: 0, errorMessage: errorMsg }
              : f
          )
        );
      }
    } catch (error) {
      if (progressInterval) clearInterval(progressInterval);
      const errorMsg =
        error instanceof Error
          ? error.message.includes('fetch')
            ? 'Cannot reach backend server. Make sure it is running on the configured port.'
            : error.message
          : 'An unexpected error occurred during upload.';

      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId
            ? { ...f, status: 'error', progress: 0, errorMessage: errorMsg }
            : f
        )
      );
    }
  };

  const removeFile = (id: string) => {
    setFiles((prev) => {
      const target = prev.find((file) => file.id === id);
      if (target?.pdfUrl) {
        URL.revokeObjectURL(target.pdfUrl);
      }
      return prev.filter((file) => file.id !== id);
    });
  };

  const completedCount = files.filter((f) => f.status === 'completed').length;
  const errorCount = files.filter((f) => f.status === 'error').length;
  const processingCount = files.filter((f) => f.status === 'processing').length;

  return (
    <div className="space-y-6">
      {/* Upload Area */}
      <div
        onClick={handleZoneClick}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-300 group ${
          isDragActive
            ? 'drag-active-overlay border-primary'
            : 'border-border hover:border-primary/50 hover:bg-primary/2'
        }`}
        id="file-upload-dropzone"
      >
        <div className="flex flex-col items-center gap-4">
          <div
            className={`p-4 rounded-2xl transition-all duration-300 ${
              isDragActive
                ? 'bg-primary/20 scale-110'
                : 'bg-primary/10 group-hover:bg-primary/15 group-hover:scale-105'
            }`}
          >
            <Upload
              className={`transition-colors duration-300 ${
                isDragActive ? 'text-primary' : 'text-primary/70'
              }`}
              size={28}
            />
          </div>
          <div>
            <p className="text-foreground font-semibold text-lg">
              {isDragActive ? 'Drop your files here' : 'Drop files here or click to upload'}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              CSV, Excel, JSON, PDF, MD, TXT — up to {MAX_FILE_SIZE_MB}MB
            </p>

          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ACCEPTED_FORMATS}
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                addFiles(Array.from(e.target.files));
                // Reset input so the same file can be re-selected
                e.target.value = '';
              }
            }}
            className="hidden"
            id="file-input"
          />
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
            className="mt-1 px-6 py-2.5 bg-primary text-white rounded-lg hover:bg-primary-hover transition-all duration-200 font-medium shadow-lg shadow-primary/25 hover:shadow-primary/40 active:scale-97"
            id="file-select-button"
          >
            Select Files
          </button>
        </div>
      </div>

      {/* Upload Summary */}
      {files.length > 0 && (
        <div className="flex items-center gap-4 text-sm">
          <h3 className="text-foreground font-semibold text-base">Uploaded Files</h3>
          <div className="flex items-center gap-3 ml-auto">
            {processingCount > 0 && (
              <span className="flex items-center gap-1.5 text-warning">
                <Clock size={14} />
                {processingCount} processing
              </span>
            )}
            {completedCount > 0 && (
              <span className="flex items-center gap-1.5 text-success">
                <CheckCircle size={14} />
                {completedCount} completed
              </span>
            )}
            {errorCount > 0 && (
              <span className="flex items-center gap-1.5 text-danger">
                <AlertCircle size={14} />
                {errorCount} failed
              </span>
            )}
          </div>
        </div>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-3">
          {files.map((file, index) => (
            <FileItem
              key={file.id}
              file={file}
              onRemove={removeFile}
              index={index}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface FileItemProps {
  file: UploadedFile;
  onRemove: (id: string) => void;
  index: number;
}

function FileItem({ file, onRemove, index }: FileItemProps) {
  const statusConfig = {
    processing: {
      icon: Clock,
      color: 'text-warning',
      bg: 'bg-warning/10',
      borderColor: 'border-warning/20',
      label: 'Processing...',
    },
    completed: {
      icon: CheckCircle,
      color: 'text-success',
      bg: 'bg-success/10',
      borderColor: 'border-success/20',
      label: 'Complete',
    },
    error: {
      icon: AlertCircle,
      color: 'text-danger',
      bg: 'bg-danger/10',
      borderColor: 'border-danger/20',
      label: 'Failed',
    },
  };

  const config = statusConfig[file.status];
  const StatusIcon = config.icon;

  const fileExt = getFileExtension(file.name);
  const isSpreadsheet = ['.csv', '.xlsx', '.xls'].includes(fileExt);
  const FileIcon = isSpreadsheet ? FileSpreadsheet : File;
  const csvPreview = file.csvPreview;

  return (
    <div
      className={`flex items-center gap-4 p-4 rounded-xl border transition-all duration-300 hover:border-border-hover animate-slide-in-right ${config.bg} ${config.borderColor}`}
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      <div className="p-2 rounded-lg bg-secondary">
        <FileIcon size={20} className="text-muted-foreground shrink-0" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-foreground font-medium truncate">{file.name}</p>
          <span className="text-xs text-muted-foreground shrink-0">{file.size}</span>
        </div>
        {file.errorMessage && (
          <p className="text-xs text-danger mt-1">{file.errorMessage}</p>
        )}
        {file.status === 'completed' && file.rowsProcessed && (
          <div className="mt-1">
            <p className="text-xs text-success">
              ✓ {file.rowsProcessed} rows processed and uploaded to knowledge base
              {file.vectorsStored !== undefined && (
                <span className="ml-2 text-sm text-muted-foreground">• {file.vectorsStored} vectors</span>
              )}
            </p>
            {file.embeddingStatus && (
              <p className="text-xs text-foreground mt-1">{file.embeddingStatus}</p>
            )}
          </div>
        )}
        {file.status !== 'error' && file.extension === '.csv' && csvPreview && csvPreview.headers.length > 0 && (
          <div className="mt-4 overflow-x-auto rounded-xl border border-border bg-secondary/20">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-secondary/60 text-muted-foreground uppercase tracking-wider">
                <tr>
                  {csvPreview.headers.map((header) => (
                    <th key={header} className="px-3 py-2 font-medium border-b border-border/50 whitespace-nowrap">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {csvPreview.rows.map((row, rowIndex) => (
                  <tr key={`${file.id}-row-${rowIndex}`} className="border-b border-border/30 last:border-b-0">
                    {csvPreview.headers.map((header) => (
                      <td key={`${file.id}-row-${rowIndex}-${header}`} className="px-3 py-2 text-foreground whitespace-nowrap align-top">
                        {row[header] || '-'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {file.status !== 'error' && file.extension === '.pdf' && file.pdfUrl && (
          <div className="mt-3 flex items-center gap-3">
            <a
              href={file.pdfUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary text-foreground text-xs font-medium hover:bg-card-hover transition-all duration-200"
            >
              <Eye size={14} />
              Preview PDF
            </a>
            <span className="text-xs text-muted-foreground">Opens the uploaded PDF in a new tab.</span>
          </div>
        )}
        {file.status === 'processing' && (
          <div className="flex items-center gap-3 mt-2">
            <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
              <div
                className="h-full bg-linear-to-br from-primary to-accent rounded-full progress-bar-animated"
                style={{ width: `${file.progress}%` }}
              />
            </div>
            <span className="text-xs text-muted-foreground tabular-nums w-8 text-right">
              {Math.round(file.progress)}%
            </span>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <div className={`px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1.5 ${config.bg} ${config.color}`}>
          <StatusIcon size={12} />
          {config.label}
        </div>
        {file.status !== 'processing' && (
          <button
            onClick={() => onRemove(file.id)}
            className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-all duration-200"
            aria-label={`Remove ${file.name}`}
          >
            <X size={16} />
          </button>
        )}
      </div>
    </div>
  );
}
