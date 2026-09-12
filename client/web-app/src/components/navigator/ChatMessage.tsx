import React from 'react';
import type { ChatMessageItem } from '../../data/mockChatData';
import { ConfidenceBadge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Sparkles, User, ShieldCheck } from 'lucide-react';
import { useAppStore } from '../../stores/useAppStore';
import { conflictBriefingItem } from '../../data/briefingData';
import { formatConversationTimestamp } from '../../lib/conversationTimestamp';
import { useTranslation } from '../../i18n/useTranslation';

interface ChatMessageProps {
  message: ChatMessageItem;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.sender === 'user';
  const { openModal } = useAppStore();
  const { language } = useTranslation();

  const handleActionClick = (actionType: string) => {
    if (actionType === 'compare_conflict' || actionType === 'draft_mentor_msg') {
      openModal('conflict_compare', conflictBriefingItem);
    }
  };

  return (
    <div className={`flex gap-3 text-xs ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
          isUser
            ? 'bg-[#3B7AB8] text-white'
            : 'bg-[#0F1F38] text-white'
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4 text-[#E1EBFA]" />}
      </div>

      {/* Bubble Container */}
      <div className={`space-y-2 max-w-[85%] ${isUser ? 'text-right' : 'text-left'}`}>
        <div
          className={`p-3.5 rounded-2xl text-xs leading-relaxed space-y-2 ${
            isUser
              ? 'bg-[#0F1F38] text-white rounded-tr-none'
              : 'bg-[#EBEFF8] text-[#0F1F38] border border-[#D5DDEB] rounded-tl-none shadow-2xs'
          }`}
        >
          {/* Message Text */}
          <div className="whitespace-pre-wrap font-sans">{message.text}</div>

          {/* Traceable Source Reference & Confidence (Required for all AI responses) */}
          {!isUser && message.sourceReference && (
            <div className="pt-2 border-t border-[#D5DDEB] space-y-1.5 text-[11px] text-[#5A6A85] bg-white p-2.5 rounded-xl border border-[#D5DDEB]/80">
              <div className="flex items-center justify-between flex-wrap gap-1">
                <span className="font-bold text-[#0F1F38] flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-[#2A6B4F]" /> Source: {message.sourceReference.platform}
                </span>
                <ConfidenceBadge level={message.sourceReference.confidence} />
              </div>
              <p className="text-[10px] text-[#8B98AB]">
                Channel: {message.sourceReference.location} · {message.sourceReference.timestamp}
              </p>
              {message.sourceReference.rawQuote && (
                <p className="text-[10px] italic text-[#0F1F38] bg-[#EDF2FB] p-1.5 rounded border border-[#D5DDEB]">
                  "{message.sourceReference.rawQuote}"
                </p>
              )}
            </div>
          )}
        </div>

        {/* Action Buttons if available */}
        {!isUser && message.actions && message.actions.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap pt-1">
            {message.actions.map((act, idx) => (
              <Button
                key={idx}
                variant="outline"
                size="sm"
                onClick={() => handleActionClick(act.actionType)}
                className="text-xs font-semibold shadow-xs"
              >
                {act.label}
              </Button>
            ))}
          </div>
        )}

        {/* Timestamp */}
        <span className="text-[10px] text-[#8B98AB] px-1 block">
          {formatConversationTimestamp(message.timestamp, language)}
        </span>
      </div>
    </div>
  );
};
