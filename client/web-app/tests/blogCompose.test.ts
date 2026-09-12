/**
 * Kiểm thử parse markdown blog phía client (không cần React).
 * Chạy: npm test
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  buildMarkdownImage,
  insertMarkdownSnippet,
  looksLikeMarkdown,
  markdownToBlocks,
  parseInlineMarkdown,
  parseMarkdownDraft,
  slugify,
} from '../src/lib/blogCompose.ts';

describe('blogCompose', () => {
  it('slugify strips punctuation', () => {
    assert.equal(slugify('Hello Mondaiy!'), 'hello-mondaiy');
  });

  it('parses frontmatter into draft fields', () => {
    const draft = parseMarkdownDraft(`---
title: Hello Mondaiy
title_vi: Xin chào
slug: hello-mondaiy
author: Admin
tags: product, design
excerpt: Short
---

# Ignored

Body one.

Body two.
`);
    assert.equal(draft.title, 'Hello Mondaiy');
    assert.equal(draft.titleVi, 'Xin chào');
    assert.equal(draft.slug, 'hello-mondaiy');
    assert.deepEqual(draft.tags, ['product', 'design']);
    assert.match(draft.body, /Body one/);
  });

  it('markdownToBlocks recognizes headings and lists', () => {
    const blocks = markdownToBlocks(`# Title

- one
- two

Paragraph here.
`);
    assert.equal(blocks[0]?.type, 'h1');
    assert.equal(blocks[1]?.type, 'ul');
    assert.equal(blocks[2]?.type, 'p');
  });

  it('markdownToBlocks recognizes numbered lists as separate items', () => {
    // Regression: câu trả lời agenda/task của LLM hay đánh số "1. ... 2. ...",
    // không có nhánh riêng thì rơi xuống đoạn văn mặc định và bị nối bằng dấu
    // cách — các việc dính hết vào nhau trên một dòng.
    const blocks = markdownToBlocks(`1. [CP2] Việc một - Hạn 12/08/2026. [Link](https://a.test)
2. [Sprint 2] Việc hai - Hạn 15/08/2026. [Link](https://b.test)
3. Việc ba - Chưa có hạn chót.
`);
    assert.equal(blocks[0]?.type, 'ol');
    if (blocks[0]?.type === 'ol') {
      assert.deepEqual(blocks[0].items, [
        '[CP2] Việc một - Hạn 12/08/2026. [Link](https://a.test)',
        '[Sprint 2] Việc hai - Hạn 15/08/2026. [Link](https://b.test)',
        'Việc ba - Chưa có hạn chót.',
      ]);
    }
  });

  it('markdownToBlocks recognizes image lines', () => {
    const blocks = markdownToBlocks(`Intro paragraph.

![Diagram](https://cdn.example/a.png)

More text.
`);
    assert.equal(blocks[0]?.type, 'p');
    assert.equal(blocks[1]?.type, 'img');
    if (blocks[1]?.type === 'img') {
      assert.equal(blocks[1].alt, 'Diagram');
      assert.equal(blocks[1].src, 'https://cdn.example/a.png');
    }
    assert.equal(blocks[2]?.type, 'p');
  });

  it('buildMarkdownImage and insertMarkdownSnippet place image markup', () => {
    const snippet = buildMarkdownImage('Hello [x]', 'https://a.test/x.png');
    assert.equal(snippet, '![Hello x](https://a.test/x.png)');
    const { next, cursor } = insertMarkdownSnippet('Before', snippet, 6, 6);
    assert.match(next, /Before\n\n!\[Hello x\]\(https:\/\/a\.test\/x\.png\)\n/);
    assert.ok(cursor > 6);
  });

  it('looksLikeMarkdown treats a plain numbered list as markdown', () => {
    // Không có bold/link/heading nào khác — chỉ số thứ tự — vẫn phải đi qua
    // markdownToBlocks, không thì rơi xuống nhánh chỉ tách theo \n\n và các
    // việc đánh số dính chung một đoạn.
    assert.equal(looksLikeMarkdown('1. Việc một\n2. Việc hai\n3. Việc ba'), true);
  });

  it('parseInlineMarkdown handles bold italic code link', () => {
    const segs = parseInlineMarkdown('A **bold** and *italic* plus `code` and [x](https://a.test)');
    assert.deepEqual(
      segs.map((s) => s.kind),
      ['text', 'bold', 'text', 'italic', 'text', 'code', 'text', 'link'],
    );
    assert.equal(segs.find((s) => s.kind === 'bold')?.text, 'bold');
    assert.equal(segs.find((s) => s.kind === 'link' && 'href' in s)?.href, 'https://a.test');
  });
});
