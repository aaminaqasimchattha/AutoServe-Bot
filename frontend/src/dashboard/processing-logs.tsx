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

  const logs: Log[] = [];

  const statusConfig = {
    completed: {
      icon: CheckCircle,
      color: 'text-success',
      badge:
        'bg-success/10 text-success border border-success/20',
      label: 'Done',
    },
    processing: {
      icon: Clock,
      color: 'text-warning',
      badge:
        'bg-warning/10 text-warning border border-warning/20',
      label: 'Processing',
    },
    error: {
      icon: AlertCircle,
      color: 'text-danger',
      badge:
        'bg-danger/10 text-danger border border-danger/20',
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
      <div className="p-6 border-b border-border">
        <h2 className="text-lg font-semibold text-foreground tracking-tight">
          Processing Logs
        </h2>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border/50 bg-secondary/30">
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
                  className="border-b border-border/30 hover:bg-secondary/30 transition-colors duration-150"
                >
                  <td className="px-6 py-4 text-sm text-foreground font-medium">
                    {log.fileName}
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-xs px-2 py-1 rounded-full bg-secondary text-muted-foreground capitalize font-medium">
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
      <div className="px-6 py-4 border-t border-border/50 flex items-center justify-between bg-secondary/20">
        <p className="text-sm text-muted-foreground">
          Showing {startIdx + 1} to{' '}
          {Math.min(startIdx + itemsPerPage, logs.length)} of {logs.length}
        </p>
        <div className="flex gap-1.5">
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="px-3 py-1.5 text-sm bg-secondary text-foreground rounded-lg hover:bg-card-hover disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200"
          >
            Previous
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
            <button
              key={page}
              onClick={() => setCurrentPage(page)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-all duration-200 ${
                page === currentPage
                  ? 'bg-linear-to-br from-primary to-accent text-white shadow-md'
                  : 'bg-secondary text-foreground hover:bg-card-hover'
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
            className="px-3 py-1.5 text-sm bg-secondary text-foreground rounded-lg hover:bg-card-hover disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
