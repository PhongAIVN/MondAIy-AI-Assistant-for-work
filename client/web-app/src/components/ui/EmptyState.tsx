import React from 'react';
import { Button } from './Button';
import { Inbox } from 'lucide-react';

export interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionLabel,
  onAction,
  icon = <Inbox className="w-10 h-10 text-[#8B98AB]" />,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center bg-white rounded-xl border border-[#D5DDEB]">
      <div className="p-3 bg-[#EBEFF8] rounded-full mb-3">{icon}</div>
      <h3 className="text-base font-bold text-[#0F1F38] font-heading">{title}</h3>
      <p className="text-xs text-[#5A6A85] max-w-sm mt-1 mb-4">{description}</p>
      {actionLabel && onAction && (
        <Button variant="outline" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};
