/**
 * Kiểm thử catalog blog quản lý.
 * Chạy: npm test
 */

import assert from 'node:assert/strict';
import { beforeEach, describe, it } from 'node:test';

const mem = new Map<string, string>();
(globalThis as { localStorage?: Storage }).localStorage = {
  getItem: (k: string) => mem.get(k) ?? null,
  setItem: (k: string, v: string) => {
    mem.set(k, v);
  },
  removeItem: (k: string) => {
    mem.delete(k);
  },
  clear: () => mem.clear(),
  key: () => null,
  length: 0,
};

const {
  listManagedBlogPosts,
  upsertManagedBlogPost,
  deleteManagedBlogPost,
  getManagedBlogPostBySlug,
  createBlogPostId,
} = await import('../src/lib/managedBlogCatalog.ts');

describe('managedBlogCatalog', () => {
  beforeEach(() => {
    mem.clear();
  });

  it('lists seed posts by default', () => {
    const posts = listManagedBlogPosts();
    assert.ok(posts.length >= 4);
    assert.ok(posts.every((p) => p.origin === 'seed'));
  });

  it('edits a seed post via override', () => {
    const first = listManagedBlogPosts()[0];
    assert.ok(first);
    upsertManagedBlogPost({
      ...first,
      title: 'Edited seed title',
    });
    const again = getManagedBlogPostBySlug(first.slug);
    assert.equal(again?.title, 'Edited seed title');
    assert.equal(again?.origin, 'seed');
  });

  it('deletes seed and adds custom post', () => {
    const first = listManagedBlogPosts()[0];
    assert.ok(first);
    deleteManagedBlogPost(first.id);
    assert.equal(getManagedBlogPostBySlug(first.slug), null);

    const custom = upsertManagedBlogPost({
      id: createBlogPostId(),
      slug: 'brand-new-post',
      title: 'Brand new',
      titleVi: 'Moi',
      excerpt: 'e',
      excerptVi: 'e',
      body: 'body',
      bodyVi: 'body',
      author: 'Admin',
      publishedAt: '2026-08-09',
      tags: ['ops'],
      coverImageUrl: null,
    });
    assert.equal(custom.origin, 'custom');
    assert.ok(listManagedBlogPosts().some((p) => p.slug === 'brand-new-post'));
  });
});
