'use client';

import { useState } from 'react';
import { Link as LinkIcon, Plus, X } from 'lucide-react';

interface UploadedUrl {
  id: string;
  url: string;
  domain: string;
  status: 'processing' | 'completed' | 'error';
}

export function UrlUpload() {
  const [urls, setUrls] = useState<UploadedUrl[]>([]);
  const [input, setInput] = useState('');
  const [error, setError] = useState('');

  const isValidUrl = (string: string) => {
    try {
      new URL(string);
      return true;
    } catch {
      return false;
    }
  };

  const handleAdd = () => {
    if (!input.trim()) {
      setError('Please enter a URL');
      return;
    }

    if (!isValidUrl(input)) {
      setError('Please enter a valid URL (e.g., https://example.com)');
      return;
    }

    const url = new URL(input);
    const newUrl: UploadedUrl = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      url: input,
      domain: url.hostname,
      status: 'processing',
    };

    setUrls((prev) => [...prev, newUrl]);
    setInput('');
    setError('');
  };

  const removeUrl = (id: string) => {
    setUrls((prev) => prev.filter((u) => u.id !== id));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleAdd();
    }
  };

  return (
    <div className="space-y-6">
      {/* Input Area */}
      <div className="space-y-3">
        <label className="block text-foreground font-semibold">
          Add URLs
        </label>
        <div className="flex gap-2">
          <div className="flex-1">
            <input
              type="text"
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                setError('');
              }}
              onKeyDown={handleKeyDown}
              placeholder="https://example.com"
              className="w-full px-4 py-2.5 bg-secondary text-foreground placeholder-muted-foreground rounded-xl border border-border focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all duration-200"
              id="url-input"
            />
          </div>
          <button
            onClick={handleAdd}
            className="px-5 py-2.5 bg-primary text-white rounded-xl hover:bg-primary-hover transition-all duration-200 flex items-center gap-2 font-medium shadow-lg shadow-primary/25 active:scale-[0.97]"
            id="add-url-button"
          >
            <Plus size={18} />
            Add
          </button>
        </div>
        {error && (
          <p className="text-sm text-danger">{error}</p>
        )}
      </div>

      {/* URL List */}
      {urls.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-foreground font-semibold">Added URLs</h3>
          {urls.map((url, index) => (
            <UrlItem
              key={url.id}
              url={url}
              onRemove={removeUrl}
              index={index}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface UrlItemProps {
  url: UploadedUrl;
  onRemove: (id: string) => void;
  index: number;
}

function UrlItem({ url, onRemove, index }: UrlItemProps) {
  const statusConfig = {
    processing: {
      badge: 'bg-warning/10 text-warning border-warning/20',
      text: 'Processing',
    },
    completed: {
      badge: 'bg-success/10 text-success border-success/20',
      text: 'Completed',
    },
    error: {
      badge: 'bg-danger/10 text-danger border-danger/20',
      text: 'Error',
    },
  };

  return (
    <div
      className="flex items-center gap-4 p-4 rounded-xl border border-border bg-secondary/50 hover:border-border-hover transition-all duration-300 animate-slide-in-right"
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      <div className="p-2 rounded-lg bg-accent/10">
        <LinkIcon size={18} className="text-accent" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-foreground font-medium truncate">{url.domain}</p>
        <p className="text-xs text-muted-foreground truncate">{url.url}</p>
      </div>
      <span
        className={`text-xs px-2.5 py-1 rounded-full border font-medium ${statusConfig[url.status].badge}`}
      >
        {statusConfig[url.status].text}
      </span>
      <button
        onClick={() => onRemove(url.id)}
        className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-all duration-200"
        aria-label={`Remove ${url.domain}`}
      >
        <X size={16} />
      </button>
    </div>
  );
}
