import { FileUpload } from '../dashboard/file-upload';

export default function UploadPage() {
  return (
    <div className="min-h-screen bg-gradient-mesh">
      {/* Header */}
      <header className="border-b border-border/50 backdrop-blur-md bg-background/60 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-4">
          <div className="p-2.5 rounded-xl bg-primary/15 glow-primary">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="hsl(var(--primary))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 17L12 22L22 17" stroke="hsl(var(--primary))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 12L12 17L22 12" stroke="hsl(var(--primary))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground tracking-tight">
              AutoServe Bot
            </h1>
            <p className="text-xs text-muted-foreground">
              Knowledge Base Manager
            </p>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-6 py-10">
        <div className="animate-fade-in-up space-y-2 mb-8">
          <h2 className="text-3xl font-bold text-foreground tracking-tight">
            Upload Product Data
          </h2>
          <p className="text-muted-foreground text-base">
            Upload your product catalog files to train the AI chatbot. Supported formats include CSV, Excel, JSON, PDF, and more.
          </p>
        </div>

        <div className="animate-fade-in-up glass-card rounded-2xl p-8" style={{ animationDelay: '0.1s' }}>
          <FileUpload />
        </div>

        {/* Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
          <div className="glass-card rounded-xl p-5 space-y-2">
            <div className="p-2 rounded-lg bg-primary/10 w-fit">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--primary))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-foreground">Supported Formats</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              CSV, Excel (.xlsx, .xls), JSON, PDF, Markdown, TXT, and DOCX files up to 50MB each.
            </p>
          </div>

          <div className="glass-card rounded-xl p-5 space-y-2">
            <div className="p-2 rounded-lg bg-accent/10 w-fit">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--accent))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-foreground">How It Works</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Files are processed, embedded into vectors, and stored in Pinecone for instant AI-powered product search.
            </p>
          </div>

          <div className="glass-card rounded-xl p-5 space-y-2">
            <div className="p-2 rounded-lg bg-success/10 w-fit">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--success))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-foreground">Instant Updates</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Once uploaded, your chatbot immediately uses the new data to answer customer queries on WhatsApp.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
