'use client';

import { Send, Bot, User } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export function ChatPreview() {
  const messages: Message[] = [];

  return (
    <div className="glass-card rounded-xl p-6 flex flex-col h-full">
      <div className="flex items-center gap-2 mb-4">
        <div className="p-1.5 rounded-lg bg-linear-to-br from-primary to-accent">
          <Bot size={16} className="text-white" />
        </div>
        <h2 className="text-lg font-semibold text-foreground tracking-tight">
          Chat Preview
        </h2>
        <span className="ml-auto text-xs text-muted-foreground bg-secondary px-2 py-1 rounded-full">
          Zara AI
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-3 overflow-y-auto mb-4 pr-1">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex gap-2 ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {message.role === 'assistant' && (
              <div className="w-6 h-6 rounded-full bg-linear-to-br from-primary to-accent flex items-center justify-center shrink-0 mt-0.5">
                <Bot size={12} className="text-white" />
              </div>
            )}
            <div
              className={`max-w-85percent px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                message.role === 'user'
                  ? 'bg-linear-to-br from-primary to-primary-hover text-white rounded-br'
                  : 'bg-secondary text-foreground rounded-bl border border-border'
              }`}
            >
              {message.content}
            </div>
            {message.role === 'user' && (
              <div className="w-6 h-6 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-0.5 border border-border">
                <User size={12} className="text-muted-foreground" />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Ask Zara a question..."
          className="flex-1 px-4 py-2.5 bg-secondary text-foreground placeholder-muted-foreground rounded-xl border border-border focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all duration-200 text-sm"
          id="chat-input"
        />
        <button
          className="p-2.5 bg-linear-to-br from-primary to-accent text-white rounded-xl hover:opacity-90 transition-opacity shadow-lg shadow-primary/30"
          id="chat-send-button"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
