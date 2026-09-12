import React from 'react';
import { HelpCircle } from 'lucide-react';

interface SuggestedQuestionProps {
  question: string;
  onClick: () => void;
}

export const SuggestedQuestion: React.FC<SuggestedQuestionProps> = ({ question, onClick }) => {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#EBEFF8] hover:bg-[#E1EBFA] text-[#0F1F38] text-xs font-semibold rounded-xl border border-[#D5DDEB] hover:border-[#2563A6] transition-all cursor-pointer text-left shrink-0 active:scale-98"
    >
      <HelpCircle className="w-3.5 h-3.5 text-[#2563A6] shrink-0" />
      <span>{question}</span>
    </button>
  );
};
