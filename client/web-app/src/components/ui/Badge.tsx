import React from 'react';
import { type ConfidenceLevel, type CommitmentLevel, type PriorityLevel } from '../../types/briefing';
import { CheckCircle2, HelpCircle, AlertTriangle, ShieldCheck, FileEdit, Clock, Sparkles, Tag } from 'lucide-react';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'purple';
  size?: 'sm' | 'md';
  icon?: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'sm',
  icon,
  className = '',
}) => {
  const styles = {
    neutral: 'bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)] border-[var(--color-border)]',
    info: 'bg-[var(--color-info-soft)] text-[var(--color-info)] border-[var(--color-border)]',
    success: 'bg-[var(--color-success-soft)] text-[var(--color-success)] border-[var(--color-border)]',
    warning: 'bg-[var(--color-warning-soft)] text-[var(--color-warning)] border-[var(--color-border)]',
    danger: 'bg-[var(--color-danger-soft)] text-[var(--color-danger)] border-[var(--color-border)]',
    purple: 'bg-[var(--color-accent-soft)] text-[var(--color-primary)] border-[var(--color-border)]',
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-xs font-medium rounded-md gap-1',
    md: 'px-2.5 py-1 text-xs font-semibold rounded-lg gap-1.5',
  };

  return (
    <span className={`inline-flex items-center border ${styles[variant]} ${sizes[size]} ${className}`}>
      {icon && <span className="shrink-0">{icon}</span>}
      <span className="whitespace-nowrap">{children}</span>
    </span>
  );
};

export const ConfidenceBadge: React.FC<{ level: ConfidenceLevel; showTooltip?: boolean }> = ({ level }) => {
  switch (level) {
    case 'certain':
      return (
        <Badge variant="success" icon={<CheckCircle2 className="w-3.5 h-3.5" />}>
          Confidence: Certain
        </Badge>
      );
    case 'possible':
      return (
        <Badge variant="warning" icon={<HelpCircle className="w-3.5 h-3.5" />}>
          Confidence: Possible
        </Badge>
      );
    case 'ask_mentor':
      return (
        <Badge variant="danger" icon={<AlertTriangle className="w-3.5 h-3.5" />}>
          Confidence: Ask your mentor
        </Badge>
      );
  }
};

export const CommitmentBadge: React.FC<{ level: CommitmentLevel }> = ({ level }) => {
  if (level === 'committed') {
    return (
      <Badge variant="info" icon={<ShieldCheck className="w-3.5 h-3.5" />}>
        Committed
      </Badge>
    );
  }
  return (
    <Badge variant="neutral" icon={<FileEdit className="w-3.5 h-3.5" />}>
      Draft Suggestion
    </Badge>
  );
};

export const PriorityBadge: React.FC<{ priority: PriorityLevel }> = ({ priority }) => {
  switch (priority) {
    case 'urgent':
      return (
        <Badge variant="danger" icon={<Clock className="w-3.5 h-3.5" />}>
          Urgent
        </Badge>
      );
    case 'important':
      return (
        <Badge variant="info" icon={<Tag className="w-3.5 h-3.5" />}>
          Important
        </Badge>
      );
    case 'update':
      return (
        <Badge variant="success" icon={<Tag className="w-3.5 h-3.5" />}>
          Update
        </Badge>
      );
    case 'suggestion':
      return (
        <Badge variant="purple" icon={<Sparkles className="w-3.5 h-3.5" />}>
          AI Suggestion
        </Badge>
      );
  }
};
