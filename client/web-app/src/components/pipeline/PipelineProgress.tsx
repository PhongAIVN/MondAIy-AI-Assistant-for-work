import React from 'react';
import { Loader2 } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import {
  PIPELINE_NODES,
  type PipelineNode,
  type PipelineNodeProgress,
} from '../../types/pipeline';

export interface PipelineProgressProps {
  nodes: Record<PipelineNode, PipelineNodeProgress>;
  phase: string;
}

export const PipelineProgress: React.FC<PipelineProgressProps> = ({ nodes, phase }) => {
  const { t } = useTranslation();

  const isRunning = phase === 'running';
  const hasError = PIPELINE_NODES.some((node) => nodes[node].status === 'error');
  const doneCount = PIPELINE_NODES.filter((node) => nodes[node].status === 'done').length;

  if (isRunning) {
    return (
      <section
        aria-labelledby="pipeline-progress-heading"
        aria-busy="true"
        className="flex flex-col items-center justify-center py-10 px-4 text-center"
      >
        <Loader2
          className="w-9 h-9 text-[var(--color-primary)] animate-spin mb-3"
          aria-hidden="true"
        />
        <h2
          id="pipeline-progress-heading"
          className="text-sm font-extrabold text-[var(--color-text-primary)] font-heading"
        >
          {t.pipeline.running}
        </h2>
        <p className="text-xs text-[var(--color-text-secondary)] mt-1 max-w-sm">
          {t.pipeline.progressSyncHint}
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="pipeline-progress-heading" className="py-2">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2
            id="pipeline-progress-heading"
            className="text-sm font-extrabold text-[var(--color-text-primary)] font-heading"
          >
            {hasError ? t.pipeline.statusError : t.pipeline.statusDone}
          </h2>
          <p className="text-[11px] text-[var(--color-text-secondary)] mt-0.5">
            {hasError ? t.pipeline.progressErrorHint : t.pipeline.progressDoneHint}
          </p>
        </div>
        <span className="text-[11px] text-[var(--color-text-secondary)]">
          {doneCount}/{PIPELINE_NODES.length}
        </span>
      </div>
    </section>
  );
};
