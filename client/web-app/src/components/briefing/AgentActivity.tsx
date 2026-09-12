import React from 'react';
import type { AgentProgressEvent } from '../../lib/agentStream';

type AgentActivityProps = {
  events: AgentProgressEvent[];
  language: 'vi' | 'en';
  statusText?: string;
};

function agentProgressLabel(event: AgentProgressEvent, language: 'vi' | 'en'): string {
  if (language === 'vi') {
    if (event.phase === 'thinking') return 'Đang suy nghĩ';
    if (event.phase === 'calling' || event.phase === 'observing') return 'Đang xem thông tin liên quan';
    return 'Đang soạn câu trả lời';
  }

  if (event.phase === 'thinking') return 'Thinking';
  if (event.phase === 'calling' || event.phase === 'observing') return 'Looking into it';
  return 'Writing the response';
}

export const AgentActivity: React.FC<AgentActivityProps> = ({ events, language, statusText }) => {
  const fallback: AgentProgressEvent = { phase: 'thinking' };
  const currentEvent = events[events.length - 1] || fallback;

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={language === 'vi' ? 'Tiến trình xử lý của mondaiy' : 'mondaiy processing progress'}
      className="flex items-center gap-3 py-2 text-sm text-[var(--color-text-secondary)]"
    >
      <img src="/loadinggif2.gif" alt="" aria-hidden="true" className="h-8 w-8 shrink-0 object-contain" />
      <span>{statusText || agentProgressLabel(currentEvent, language)}</span>
      <span className="inline-flex gap-0.5" aria-hidden="true">
        {[0, 1, 2].map((dot) => (
          <span
            key={dot}
            className="h-1 w-1 animate-bounce rounded-full bg-[var(--color-text-muted)]"
            style={{ animationDelay: `${dot * 120}ms` }}
          />
        ))}
      </span>
    </div>
  );
};
