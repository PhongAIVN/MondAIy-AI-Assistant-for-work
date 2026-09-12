import React from 'react';
import { Button } from './Button';
import { AlertOctagon, RefreshCw, Eye } from 'lucide-react';

export interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  onViewPrevious?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Your briefing could not be updated.',
  description = 'Your previous briefing is still available.',
  onRetry,
  onViewPrevious,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center bg-[#F9DEDE] rounded-xl border border-[#E4BDB6] shadow-xs">
      <div className="p-3 bg-white rounded-full mb-3 text-[#A03D3D] shadow-xs">
        <AlertOctagon className="w-8 h-8" />
      </div>
      <h3 className="text-base font-bold text-[#0F1F38] font-heading">{title}</h3>
      <p className="text-xs text-[#5A6A85] max-w-sm mt-1 mb-5">{description}</p>
      <div className="flex items-center gap-3">
        {onRetry && (
          <Button variant="danger" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />} onClick={onRetry}>
            Retry
          </Button>
        )}
        {onViewPrevious && (
          <Button variant="outline" size="sm" icon={<Eye className="w-3.5 h-3.5" />} onClick={onViewPrevious}>
            View previous briefing
          </Button>
        )}
      </div>
    </div>
  );
};
