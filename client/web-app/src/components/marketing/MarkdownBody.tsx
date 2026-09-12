import React from 'react';
import { looksLikeMarkdown, markdownToBlocks, parseInlineMarkdown } from '../../lib/blogCompose';

type MarkdownTextProps = {
  text: string;
  className?: string;
};

/** Render inline markdown: **bold**, *italic*, `code`, ~~strike~~, [link](url). */
export const MarkdownText: React.FC<MarkdownTextProps> = ({ text, className }) => {
  const segments = parseInlineMarkdown(text);
  return (
    <span className={className}>
      {segments.map((seg, idx) => {
        const key = `${seg.kind}-${idx}`;
        if (seg.kind === 'bold') return <strong key={key}>{seg.text}</strong>;
        if (seg.kind === 'italic') return <em key={key}>{seg.text}</em>;
        if (seg.kind === 'strike') return <s key={key}>{seg.text}</s>;
        if (seg.kind === 'code') {
          return (
            <code
              key={key}
              className="rounded bg-ink-900/8 px-1 py-0.5 font-mono text-[0.9em] text-ink-800"
            >
              {seg.text}
            </code>
          );
        }
        if (seg.kind === 'link') {
          return (
            <a
              key={key}
              href={seg.href}
              target="_blank"
              rel="noreferrer"
              className="font-semibold text-action-solid underline-offset-2 hover:underline"
            >
              {seg.text}
            </a>
          );
        }
        return <React.Fragment key={key}>{seg.text}</React.Fragment>;
      })}
    </span>
  );
};

type MarkdownBodyProps = {
  source: string;
  className?: string;
};

/** Render body blog: headings / list / quote / code / image + inline formatting. */
export const MarkdownBody: React.FC<MarkdownBodyProps> = ({ source, className }) => {
  if (!source.trim()) return null;

  if (!looksLikeMarkdown(source)) {
    return (
      <div className={className ?? 'space-y-5 text-base leading-relaxed text-ink-700'}>
        {source.split(/\n\n+/).map((paragraph) => (
          <p key={paragraph.slice(0, 32)} className="text-pretty">
            <MarkdownText text={paragraph} />
          </p>
        ))}
      </div>
    );
  }

  const blocks = markdownToBlocks(source);
  return (
    <div className={className ?? 'space-y-5 text-base leading-relaxed text-ink-700'}>
      {blocks.map((block, idx) => {
        const key = `${block.type}-${idx}`;
        if (block.type === 'h1') {
          return (
            <h2 key={key} className="text-2xl font-semibold text-ink-900">
              <MarkdownText text={block.text} />
            </h2>
          );
        }
        if (block.type === 'h2') {
          return (
            <h3 key={key} className="text-xl font-semibold text-ink-900">
              <MarkdownText text={block.text} />
            </h3>
          );
        }
        if (block.type === 'h3') {
          return (
            <h4 key={key} className="text-lg font-semibold text-ink-900">
              <MarkdownText text={block.text} />
            </h4>
          );
        }
        if (block.type === 'quote') {
          return (
            <blockquote key={key} className="border-l-2 border-action-solid/40 pl-4 italic text-ink-500">
              <MarkdownText text={block.text} />
            </blockquote>
          );
        }
        if (block.type === 'ul') {
          return (
            <ul key={key} className="list-disc space-y-1 pl-5">
              {block.items.map((item) => (
                <li key={item}>
                  <MarkdownText text={item} />
                </li>
              ))}
            </ul>
          );
        }
        if (block.type === 'ol') {
          return (
            <ol key={key} className="list-decimal space-y-1 pl-5">
              {block.items.map((item) => (
                <li key={item}>
                  <MarkdownText text={item} />
                </li>
              ))}
            </ol>
          );
        }
        if (block.type === 'code') {
          return (
            <pre
              key={key}
              className="overflow-x-auto rounded-lg bg-ink-900/90 p-3 font-mono text-xs text-paper-raised"
            >
              {block.text}
            </pre>
          );
        }
        if (block.type === 'img') {
          return (
            <figure key={key} className="overflow-hidden rounded-xl">
              <img
                src={block.src}
                alt={block.alt || ''}
                className="mx-auto max-h-[32rem] w-full object-contain"
                loading="lazy"
              />
              {block.alt ? (
                <figcaption className="mt-2 text-center text-xs text-ink-400">{block.alt}</figcaption>
              ) : null}
            </figure>
          );
        }
        return (
          <p key={key} className="text-pretty">
            <MarkdownText text={block.text} />
          </p>
        );
      })}
    </div>
  );
};
