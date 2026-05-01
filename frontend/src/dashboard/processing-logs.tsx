'use client';

import { CheckCircle, AlertCircle, Clock } from 'lucide-react';
import { useState } from 'react';

interface Log {
  id: string;
  fileName: string;
  type: 'file' | 'url';
  size: string;
  status: 'completed' | 'processing' | 'error';
  chunks: number;
  duration: string;
  timestamp: string;
}

export function ProcessingLogs() {
  const [currentPage, setCurrentPage] = useState(1);

  const logs: Log[] = [
    {
      id: '1',
      fileName: 'electronics_2024.csv',
      type: 'file',
      size: '2.4 MB',
      status: 'completed',
      chunks: 48,
      duration: '2.3s',
      timestamp: '2024-01-15 10:23',
    },
    {
      id: '2',
      fileName: 'gadgets_q4.xlsx',
      type: 'file',
      size: '1.8 MB',
      status: 'completed',
      chunks: 36,
      duration: '1.9s',
      timestamp: '2024-01-15 10:15',
    },
    {
      id: '3',
      fileName: 'docs.autoserve.bot',
      type: 'url',
      size: '3.2 MB',
      status: 'processing',
      chunks: 64,
      duration: '1.2s',
      timestamp: '2024-01-15 10:05',
    },
    {
      id: '4',
      fileName: 'products_batch.json',
      type: 'file',
      size: '890 KB',
      status: 'completed',
      chunks: 18,
      duration: '0.8s',
      timestamp: '2024-01-15 09:45',
    },
    {
      id: '5',
      fileName: 'archive_backup.zip',
      type: 'file',
      size: '5.1 MB',
      status: 'error',
      chunks: 0,
      duration: 'Failed',
      timestamp: '2024-01-15 09:30',
    },
  ];

  const statusConfig = {
    completed: {
      icon: CheckCircle,
      color: 'text-[hsl(var(--success))]',
      badge:
        'bg-[hsl(var(--success)/0.1)] text-[hsl(var(--success))] border border-[hsl(var(--success)/0.2)]',
      label: 'Done',
    },
    processing: {
      icon: Clock,
      color: 'text-[hsl(var(--warning))]',
      badge:
        'bg-[hsl(var(--warning)/0.1)] text-[hsl(var(--warning))] border border-[hsl(var(--warning)/0.2)]',
      label: 'Processing',
    },
    error: {
      icon: AlertCircle,
      color: 'text-[hsl(var(--danger))]',
      badge:
        'bg-[hsl(var(--danger)/0.1)] text-[hsl(var(--danger))] border border-[hsl(var(--danger)/0.2)]',
      label: 'Error',
    },
  };

  const itemsPerPage = 5;
  const totalPages = Math.ceil(logs.length / itemsPerPage);
  const startIdx = (currentPage - 1) * itemsPerPage;
  const displayedLogs = logs.slice(startIdx, startIdx + itemsPerPage);

  return (
    <div className="glass-card rounded-xl overflow-hidden">
      {/* Table Header */}
      <div className="p-6 border-b border-[hsl(var(--border))]">
        <h2 className="text-lg font-semibold text-foreground tracking-tight">
          Processing Logs
        </h2>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[hsl(var(--border)/0.5)] bg-[hsl(var(--secondary)/0.3)]">
              <th className="px-6 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                File Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Type
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Size
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Chunks
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Duration
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {displayedLogs.map((log) => {
              const config = statusConfig[log.status];
              const StatusIcon = config.icon;
              return (
                <tr
                  key={log.id}
                  className="border-b border-[hsl(var(--border)/0.3)] hover:bg-[hsl(var(--secondary)/0.3)] transition-colors duration-150"
                >
                  <td className="px-6 py-4 text-sm text-foreground font-medium">
                    {log.fileName}
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-xs px-2 py-1 rounded-full bg-[hsl(var(--secondary))] text-muted-foreground capitalize font-medium">
                      {log.type}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-muted-foreground tabular-nums">
                    {log.size}
                  </td>
                  <td className="px-6 py-4 text-sm text-muted-foreground tabular-nums">
                    {log.chunks}
                  </td>
                  <td className="px-6 py-4 text-sm text-muted-foreground tabular-nums">
                    {log.duration}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5">
                      <StatusIcon size={14} className={config.color} />
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${config.badge}`}
                      >
                        {config.label}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="px-6 py-4 border-t border-[hsl(var(--border)/0.5)] flex items-center justify-between bg-[hsl(var(--secondary)/0.2)]">
        <p className="text-sm text-muted-foreground">
          Showing {startIdx + 1} to{' '}
          {Math.min(startIdx + itemsPerPage, logs.length)} of {logs.length}
        </p>
        <div className="flex gap-1.5">
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="px-3 py-1.5 text-sm bg-[hsl(var(--secondary))] text-foreground rounded-lg hover:bg-[hsl(var(--card-hover))] disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200"
          >
            Previous
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
            <button
              key={page}
              onClick={() => setCurrentPage(page)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-all duration-200 ${
                page === currentPage
                  ? 'bg-gradient-to-r from-[hsl(var(--primary))] to-[hsl(var(--accent))] text-white shadow-md'
                  : 'bg-[hsl(var(--secondary))] text-foreground hover:bg-[hsl(var(--card-hover))]'
              }`}
            >
              {page}
            </button>
          ))}
          <button
            onClick={() =>
              setCurrentPage((p) => Math.min(totalPages, p + 1))
            }
            disabled={currentPage === totalPages}
            className="px-3 py-1.5 text-sm bg-[hsl(var(--secondary))] text-foreground rounded-lg hover:bg-[hsl(var(--card-hover))] disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
