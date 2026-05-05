'use client';

import { useState } from 'react';
import { FileText, Link as LinkIcon } from 'lucide-react';
import { FileUpload } from './file-upload';
import { UrlUpload } from './url-upload';

type Tab = 'files' | 'urls';

export function DataIngestion() {
  const [activeTab, setActiveTab] = useState<Tab>('files');

  return (
    <div className="glass-card rounded-xl p-6">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-foreground mb-4 tracking-tight">
          Ingest Data
        </h2>
        <div className="flex gap-1 bg-secondary rounded-xl p-1 w-fit">
          <TabButton
            active={activeTab === 'files'}
            onClick={() => setActiveTab('files')}
            icon={<FileText size={18} />}
            label="Upload Files"
          />
          <TabButton
            active={activeTab === 'urls'}
            onClick={() => setActiveTab('urls')}
            icon={<LinkIcon size={18} />}
            label="Add URLs"
          />
        </div>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'files' && <FileUpload />}
        {activeTab === 'urls' && <UrlUpload />}
      </div>
    </div>
  );
}

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}

function TabButton({ active, onClick, icon, label }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all duration-200 ${
        active
          ? 'bg-linear-to-br from-primary to-primary-hover text-white shadow-md shadow-primary/30'
          : 'text-muted-foreground hover:text-foreground hover:bg-card'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
