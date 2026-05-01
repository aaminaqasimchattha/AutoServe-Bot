import { Sidebar } from '../dashboard/sidebar';
import { ProcessingLogs } from '../dashboard/processing-logs';
import { Header } from '../dashboard/header';
import { Overview } from '../dashboard/overview';
import { DataIngestion } from '../dashboard/data-ingestion';
import { ChatPreview } from '../dashboard/chat-preview';
import { Activity } from '../dashboard/activity';

export default function DashboardPage() {
  return (
    <div className="flex h-screen bg-gradient-mesh">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <Header />

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-8 space-y-8 max-w-[1600px] mx-auto">
            {/* Welcome Section */}
            <div className="animate-fade-in-up">
              <h1 className="text-4xl font-bold text-foreground mb-2 tracking-tight">
                Dashboard
              </h1>
              <p className="text-muted-foreground text-lg">
                Welcome back! Manage your AI chatbot knowledge base and track
                ingestion progress.
              </p>
            </div>

            {/* Overview Stats */}
            <section className="animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
              <Overview />
            </section>

            {/* Main Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left Column - Data Ingestion (Full Height) */}
              <div
                className="lg:col-span-2 space-y-8 animate-fade-in-up"
                style={{ animationDelay: '0.2s' }}
              >
                {/* Data Ingestion */}
                <DataIngestion />

                {/* Processing Logs */}
                <ProcessingLogs />
              </div>

              {/* Right Column - Chat & Activity */}
              <div
                className="space-y-8 animate-fade-in-up"
                style={{ animationDelay: '0.3s' }}
              >
                {/* Chat Preview */}
                <div className="h-[420px]">
                  <ChatPreview />
                </div>

                {/* Recent Activity */}
                <Activity />
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
