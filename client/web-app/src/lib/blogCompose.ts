/**
 * Parse markdown blog phía client — frontmatter tối giản + slug + inline.
 * Logic khớp `src/services/blog_markdown.py` để form fill ngay khi chọn file.
 */

export type ParsedBlogDraft = {
  title: string;
  titleVi: string;
  slug: string;
  author: string;
  excerpt: string;
  excerptVi: string;
  tags: string[];
  body: string;
  bodyVi: string;
};

const SLUG_RE = /[^a-z0-9]+/g;
const FRONTMATTER_RE = /^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/;

export function slugify(value: string): string {
  const cleaned = value.trim().toLowerCase().replace(SLUG_RE, '-').replace(/^-|-$/g, '');
  return cleaned.slice(0, 80) || 'untitled';
}

function parseFrontmatterBlock(block: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const line of block.split('\n')) {
    const idx = line.indexOf(':');
    if (idx < 0) continue;
    const key = line.slice(0, idx).trim().toLowerCase();
    const raw = line.slice(idx + 1).trim().replace(/^["']|["']$/g, '');
    result[key] = raw;
  }
  return result;
}

export function parseMarkdownDraft(raw: string): ParsedBlogDraft {
  const text = raw.replace(/\r\n/g, '\n').trim();
  const match = text.match(FRONTMATTER_RE);
  let meta: Record<string, string> = {};
  let body = text;
  if (match) {
    meta = parseFrontmatterBlock(match[1]);
    body = match[2].trim();
  }

  let title = meta.title || meta.title_en || '';
  if (!title) {
    for (const line of body.split('\n')) {
      const heading = line.trim();
      if (heading.startsWith('# ')) {
        title = heading.slice(2).trim();
        break;
      }
    }
  }

  const tagsRaw = meta.tags || '';
  const tags = tagsRaw
    ? tagsRaw.split(',').map((t) => t.trim()).filter(Boolean)
    : [];

  return {
    title,
    titleVi: meta.title_vi || '',
    slug: meta.slug || (title ? slugify(title) : 'untitled'),
    author: meta.author || '',
    excerpt: meta.excerpt || meta.excerpt_en || '',
    excerptVi: meta.excerpt_vi || '',
    tags,
    body,
    bodyVi: meta.body_vi || '',
  };
}

/** Chuyển markdown đơn giản thành các khối preview (không dùng lib ngoài). */
export type MarkdownBlock =
  | { type: 'h1' | 'h2' | 'h3'; text: string }
  | { type: 'p'; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] }
  | { type: 'quote'; text: string }
  | { type: 'code'; text: string }
  | { type: 'img'; alt: string; src: string };

/** Dòng chỉ chứa một ảnh markdown: ![alt](url) */
const IMAGE_LINE_RE = /^\s*!\[([^\]]*)\]\(([^)\s]+)\)\s*$/;

/** Tạo snippet ảnh để chèn vào body. */
export function buildMarkdownImage(alt: string, src: string): string {
  const safeAlt = alt.replace(/[[\]]/g, '').trim();
  return `![${safeAlt}](${src})`;
}

/** Chèn snippet markdown tại vùng chọn của textarea. */
export function insertMarkdownSnippet(
  source: string,
  snippet: string,
  selectionStart: number,
  selectionEnd: number,
): { next: string; cursor: number } {
  const start = Math.max(0, Math.min(selectionStart, source.length));
  const end = Math.max(start, Math.min(selectionEnd, source.length));
  const before = source.slice(0, start);
  const after = source.slice(end);

  let lead = '';
  if (before.length > 0 && !before.endsWith('\n\n')) {
    lead = before.endsWith('\n') ? '\n' : '\n\n';
  }
  const trail = after.length === 0 || after.startsWith('\n') ? '\n' : '\n\n';
  const insertion = `${lead}${snippet}${trail}`;
  const next = `${before}${insertion}${after}`;
  return { next, cursor: before.length + insertion.length };
}

export type InlineSeg =
  | { kind: 'text'; text: string }
  | { kind: 'bold'; text: string }
  | { kind: 'italic'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'strike'; text: string }
  | { kind: 'link'; text: string; href: string };

/** Token inline: code → link → bold → strike → italic (không gắn flag g trên const). */
const INLINE_TOKEN_SOURCE =
  '(`[^`]+`)|(\\[[^\\]]+\\]\\([^)]+\\))|(\\*\\*[^*]+\\*\\*)|(__[^_]+__)|(~~[^~]+~~)|(\\*[^*]+\\*)|(_[^_]+_)';

export function parseInlineMarkdown(source: string): InlineSeg[] {
  const segments: InlineSeg[] = [];
  let last = 0;
  const re = new RegExp(INLINE_TOKEN_SOURCE, 'g');
  let match: RegExpExecArray | null = re.exec(source);
  while (match !== null) {
    if (match.index > last) {
      segments.push({ kind: 'text', text: source.slice(last, match.index) });
    }
    const token = match[0];
    if (token.startsWith('`')) {
      segments.push({ kind: 'code', text: token.slice(1, -1) });
    } else if (token.startsWith('[')) {
      const linkMatch = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      if (linkMatch) {
        segments.push({ kind: 'link', text: linkMatch[1], href: linkMatch[2] });
      } else {
        segments.push({ kind: 'text', text: token });
      }
    } else if (token.startsWith('**') || token.startsWith('__')) {
      segments.push({ kind: 'bold', text: token.slice(2, -2) });
    } else if (token.startsWith('~~')) {
      segments.push({ kind: 'strike', text: token.slice(2, -2) });
    } else if (token.startsWith('*') || token.startsWith('_')) {
      segments.push({ kind: 'italic', text: token.slice(1, -1) });
    } else {
      segments.push({ kind: 'text', text: token });
    }
    last = match.index + token.length;
    match = re.exec(source);
  }
  if (last < source.length) {
    segments.push({ kind: 'text', text: source.slice(last) });
  }
  return segments.length > 0 ? segments : [{ kind: 'text', text: source }];
}

export function markdownToBlocks(source: string): MarkdownBlock[] {
  const lines = source.replace(/\r\n/g, '\n').split('\n');
  const blocks: MarkdownBlock[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    if (line.startsWith('```')) {
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith('```')) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1;
      blocks.push({ type: 'code', text: code.join('\n') });
      continue;
    }
    if (line.startsWith('### ')) {
      blocks.push({ type: 'h3', text: line.slice(4).trim() });
      i += 1;
      continue;
    }
    if (line.startsWith('## ')) {
      blocks.push({ type: 'h2', text: line.slice(3).trim() });
      i += 1;
      continue;
    }
    if (line.startsWith('# ')) {
      blocks.push({ type: 'h1', text: line.slice(2).trim() });
      i += 1;
      continue;
    }
    if (line.startsWith('> ')) {
      blocks.push({ type: 'quote', text: line.slice(2).trim() });
      i += 1;
      continue;
    }
    if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, '').trim());
        i += 1;
      }
      blocks.push({ type: 'ul', items });
      continue;
    }
    if (/^\s*\d+[.)]\s+/.test(line)) {
      // "1. việc A" — LLM hay trả lời task/agenda kiểu đánh số, không chỉ
      // gạch đầu dòng. Thiếu nhánh này thì rơi xuống đoạn văn bên dưới, các
      // dòng bị nối lại bằng dấu cách và trông như dính hết vào nhau.
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+[.)]\s+/, '').trim());
        i += 1;
      }
      blocks.push({ type: 'ol', items });
      continue;
    }

    const imageMatch = IMAGE_LINE_RE.exec(line);
    if (imageMatch) {
      blocks.push({ type: 'img', alt: imageMatch[1], src: imageMatch[2] });
      i += 1;
      continue;
    }

    const para: string[] = [line];
    i += 1;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^#{1,3}\s|^```|^>\s|^\s*[-*]\s+|^\s*\d+[.)]\s+|^\s*!\[/.test(lines[i])
    ) {
      para.push(lines[i]);
      i += 1;
    }
    blocks.push({ type: 'p', text: para.join(' ').trim() });
  }

  return blocks;
}

/** True nếu nội dung nên đi qua renderer markdown (block hoặc inline). */
export function looksLikeMarkdown(text: string): boolean {
  return (
    /(^|\n)#{1,3}\s|(^|\n)```|(^|\n)>\s|(^|\n)\s*[-*]\s+|(^|\n)\s*\d+[.)]\s+|!\[[^\]]*\]\([^)]+\)/.test(
      text,
    ) ||
    /(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`|~~[^~]+~~|\[[^\]]+\]\([^)]+\))/.test(text)
  );
}
