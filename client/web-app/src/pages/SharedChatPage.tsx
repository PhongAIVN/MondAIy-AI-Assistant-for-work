import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Copy, Check, ExternalLink } from 'lucide-react';
import { API_BASE_URL } from '../lib/apiClient';
import { MarkdownBody } from '../components/marketing/MarkdownBody';

type SharedMessage = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
};

type SharedChatResponse = {
  title: string;
  messages: SharedMessage[];
};

export const SharedChatPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [chat, setChat] = useState<SharedChatResponse | null>(null);
  const [error, setError] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/v1/shared-chat/${encodeURIComponent(token)}`)
      .then((response) => {
        if (!response.ok) throw new Error('shared chat unavailable');
        return response.json() as Promise<SharedChatResponse>;
      })
      .then((payload) => {
        if (!cancelled) setChat(payload);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const copyMessage = async (content: string) => {
    await navigator.clipboard?.writeText(content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  if (error) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-[#151515] px-6 text-[#e8e5df]">
        <div className="text-center">
          <p className="text-lg">Đoạn chat này không còn công khai.</p>
          <p className="mt-2 text-sm text-[#8f8c87]">Link có thể đã bị tắt hoặc không tồn tại.</p>
        </div>
      </main>
    );
  }

  if (!chat) {
    return <main className="min-h-[100dvh] bg-[#151515]" aria-label="Đang tải đoạn chat" />;
  }

  return (
    <main className="min-h-[100dvh] bg-[#151515] text-[#e8e5df]">
      <header className="flex h-16 items-center justify-between border-b border-white/[0.06] px-5 sm:px-8">
        <div className="font-display text-xl font-semibold tracking-tight">mondaiy</div>
        <div className="flex items-center gap-5 text-sm text-[#b7b3ad]">
          <span className="hidden sm:inline">{chat.title}</span>
          <a href="/" className="inline-flex items-center gap-1.5 rounded-lg bg-[#2a2a2a] px-3 py-2 text-[#e8e5df] hover:bg-[#343434]">
            Tham gia mondaiy <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </header>

      <section className="mx-auto w-full max-w-[860px] px-5 pb-32 pt-12 sm:px-8 sm:pt-16">
        <h1 className="mb-10 text-center text-sm text-[#8f8c87] sm:text-base">{chat.title}</h1>
        <div className="space-y-10">
          {chat.messages.map((message) => (
            <article key={message.id} className={message.role === 'user' ? 'flex justify-end' : 'space-y-4'}>
              {message.role === 'user' ? (
                <div className="max-w-[78%] rounded-2xl bg-[#272727] px-4 py-3 text-[15px] leading-relaxed text-[#f1eee8]">
                  {message.content}
                </div>
              ) : (
                <div className="group max-w-[820px]">
                  <MarkdownBody source={message.content} className="space-y-4 text-[15px] leading-[1.75] text-[#ddd9d2]" />
                  <button
                    type="button"
                    onClick={() => void copyMessage(message.content)}
                    className="mt-4 inline-flex items-center gap-2 rounded-lg p-2 text-[#8f8c87] opacity-70 transition hover:bg-white/[0.06] hover:text-[#e8e5df] group-hover:opacity-100"
                    aria-label="Sao chép câu trả lời"
                  >
                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      </section>
    </main>
  );
};
