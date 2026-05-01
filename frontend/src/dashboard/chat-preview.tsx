'use client';

import { Send, Bot, User } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export function ChatPreview() {
  const messages: Message[] = [
    {
      id: '1',
      role: 'user',
      content: 'Do you have any smartphones under 20000?',
    },
    {
      id: '2',
      role: 'assistant',
      content:
        'Yes! Here are some top picks: Redmi Note 13 Pro at ₹17,999 (⭐4.3), realme narzo 60 at ₹14,999 (⭐4.1). Both have great ratings and are currently on discount!',
    },
    {
      id: '3',
      role: 'user',
      content: 'What about earbuds?',
    },
    {
      id: '4',
      role: 'assistant',
      content:
        'Great choice! boAt Airdopes 141 at ₹899 (⭐4.1, 2.5L reviews) and OnePlus Bullets Z2 at ₹1,499 (⭐4.3) are our best sellers right now.',
    },
  ];

  return (
    <div className="glass-card rounded-xl p-6 flex flex-col h-full">
      <div className="flex items-center gap-2 mb-4">
        <div className="p-1.5 rounded-lg bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))]">
          <Bot size={16} className="text-white" />
        </div>
        <h2 className="text-lg font-semibold text-foreground tracking-tight">
          Chat Preview
        </h2>
        <span className="ml-auto text-xs text-muted-foreground bg-[hsl(var(--secondary))] px-2 py-1 rounded-full">
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
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bot size={12} className="text-white" />
              </div>
            )}
            <div
              className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                message.role === 'user'
                  ? 'bg-gradient-to-r from-[hsl(var(--primary))] to-[hsl(var(--primary-hover))] text-white rounded-br-md'
                  : 'bg-[hsl(var(--secondary))] text-foreground rounded-bl-md border border-[hsl(var(--border))]'
              }`}
            >
              {message.content}
            </div>
            {message.role === 'user' && (
              <div className="w-6 h-6 rounded-full bg-[hsl(var(--secondary))] flex items-center justify-center flex-shrink-0 mt-0.5 border border-[hsl(var(--border))]">
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
          className="flex-1 px-4 py-2.5 bg-[hsl(var(--secondary))] text-foreground placeholder-[hsl(var(--muted-foreground))] rounded-xl border border-[hsl(var(--border))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary)/0.5)] transition-all duration-200 text-sm"
          id="chat-input"
        />
        <button
          className="p-2.5 bg-gradient-to-r from-[hsl(var(--primary))] to-[hsl(var(--accent))] text-white rounded-xl hover:opacity-90 transition-opacity shadow-lg shadow-[hsl(var(--primary)/0.3)]"
          id="chat-send-button"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
