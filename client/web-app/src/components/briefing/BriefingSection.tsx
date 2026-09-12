import React from 'react';

export interface BriefingSectionProps {
  title: string;
  description?: string;
  badge?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

export const BriefingSection: React.FC<BriefingSectionProps> = ({
  title,
  description,
  badge,
  icon,
  children,
}) => {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between pb-2 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2.5">
          {icon && <div className="p-1.5 bg-[var(--color-accent-soft)] text-[var(--color-primary)] rounded-lg">{icon}</div>}
          <div>
            <h2 className="text-base font-extrabold text-[var(--color-text-primary)] font-heading flex items-center gap-2">
              {title}
              {badge && (
                <span className="text-xs font-semibold px-2 py-0.5 bg-[var(--color-primary)] text-white rounded-full">
                  {badge}
                </span>
              )}
            </h2>
            {description && <p className="text-xs text-[var(--color-text-secondary)]">{description}</p>}
          </div>
        </div>
      </div>

      <div className="space-y-4">{children}</div>
    </section>
  );
};
