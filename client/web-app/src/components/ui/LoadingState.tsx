import React from 'react';

export interface LoadingStateProps {
  message?: string;
  submessage?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Reviewing your connected sources...',
  submessage = 'Preparing your daily briefing...',
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-white rounded-xl border border-[#D5DDEB] shadow-xs">
      <img src="/loadinggif2.gif" alt="" aria-hidden className="w-16 h-16 mb-3" />
      <h3 className="text-sm font-bold text-[#0F1F38] font-heading">{message}</h3>
      <p className="text-xs text-[#5A6A85] mt-1">{submessage}</p>
    </div>
  );
};
