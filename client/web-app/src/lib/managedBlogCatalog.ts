/**
 * Catalog blog quản lý từ Admin: seed (blogPosts.ts) + override/xoá/thêm custom.
 * Public /blog và Admin cùng đọc từ đây.
 */

import { blogPosts, type BlogPost } from '../data/blogPosts.ts';

const CATALOG_KEY = 'mondaiy_blog_catalog_v1';
const LEGACY_PUBLISHED_KEY = 'mondaiy_published_blog_v1';

export type ManagedBlogPost = BlogPost & {
  origin: 'seed' | 'custom';
};

type CatalogState = {
  deletedSeedIds: string[];
  overrides: Record<string, BlogPost>;
  custom: BlogPost[];
};

function emptyState(): CatalogState {
  return { deletedSeedIds: [], overrides: {}, custom: [] };
}

function readState(): CatalogState {
  try {
    const raw = localStorage.getItem(CATALOG_KEY);
    if (!raw) {
      const migrated = migrateLegacyPublished();
      saveState(migrated);
      return migrated;
    }
    const parsed = JSON.parse(raw) as CatalogState;
    return {
      deletedSeedIds: Array.isArray(parsed.deletedSeedIds) ? parsed.deletedSeedIds : [],
      overrides: parsed.overrides && typeof parsed.overrides === 'object' ? parsed.overrides : {},
      custom: Array.isArray(parsed.custom) ? parsed.custom : [],
    };
  } catch {
    return emptyState();
  }
}

function saveState(state: CatalogState): void {
  localStorage.setItem(CATALOG_KEY, JSON.stringify(state));
}

function migrateLegacyPublished(): CatalogState {
  const state = emptyState();
  try {
    const raw = localStorage.getItem(LEGACY_PUBLISHED_KEY);
    if (!raw) return state;
    const legacy = JSON.parse(raw) as BlogPost[];
    if (!Array.isArray(legacy)) return state;
    const seedIds = new Set(blogPosts.map((p) => p.id));
    const seedSlugs = new Map(blogPosts.map((p) => [p.slug, p.id]));
    for (const post of legacy) {
      const seedId = seedSlugs.get(post.slug);
      if (seedId) {
        state.overrides[seedId] = { ...post, id: seedId };
      } else if (!seedIds.has(post.id)) {
        state.custom.push(post);
      } else {
        state.overrides[post.id] = post;
      }
    }
  } catch {
    // bỏ qua legacy hỏng
  }
  return state;
}

function sortByDateDesc(posts: ManagedBlogPost[]): ManagedBlogPost[] {
  return [...posts].sort((a, b) => (a.publishedAt < b.publishedAt ? 1 : a.publishedAt > b.publishedAt ? -1 : 0));
}

export function isSeedBlogId(id: string): boolean {
  return blogPosts.some((p) => p.id === id);
}

/** Danh sách bài hiện trên /blog và trong Admin. */
export function listManagedBlogPosts(): ManagedBlogPost[] {
  const state = readState();
  const deleted = new Set(state.deletedSeedIds);
  const items: ManagedBlogPost[] = [];

  for (const seed of blogPosts) {
    if (deleted.has(seed.id)) continue;
    const override = state.overrides[seed.id];
    items.push({ ...(override ?? seed), origin: 'seed' });
  }

  const seedIds = new Set(blogPosts.map((p) => p.id));
  for (const post of state.custom) {
    if (seedIds.has(post.id) || deleted.has(post.id)) continue;
    items.push({ ...post, origin: 'custom' });
  }

  return sortByDateDesc(items);
}

export function getManagedBlogPostBySlug(slug: string): ManagedBlogPost | null {
  return listManagedBlogPosts().find((p) => p.slug === slug) ?? null;
}

export function getManagedBlogPostById(id: string): ManagedBlogPost | null {
  return listManagedBlogPosts().find((p) => p.id === id) ?? null;
}

/** Tạo mới hoặc cập nhật (kể cả bài seed). */
export function upsertManagedBlogPost(post: BlogPost): ManagedBlogPost {
  const state = readState();
  const normalized: BlogPost = {
    ...post,
    titleVi: post.titleVi || post.title,
    excerptVi: post.excerptVi || post.excerpt,
    bodyVi: post.bodyVi || post.body,
    coverImageUrl: post.coverImageUrl ?? null,
  };

  if (isSeedBlogId(normalized.id)) {
    state.deletedSeedIds = state.deletedSeedIds.filter((id) => id !== normalized.id);
    state.overrides[normalized.id] = normalized;
    state.custom = state.custom.filter((p) => p.id !== normalized.id && p.slug !== normalized.slug);
    saveState(state);
    return { ...normalized, origin: 'seed' };
  }

  const without = state.custom.filter((p) => p.id !== normalized.id && p.slug !== normalized.slug);
  without.unshift(normalized);
  state.custom = without;
  // Nếu slug trùng seed đã xoá/override — giữ custom riêng
  saveState(state);
  return { ...normalized, origin: 'custom' };
}

export function deleteManagedBlogPost(id: string): void {
  const state = readState();
  if (isSeedBlogId(id)) {
    if (!state.deletedSeedIds.includes(id)) state.deletedSeedIds.push(id);
    delete state.overrides[id];
  }
  state.custom = state.custom.filter((p) => p.id !== id);
  saveState(state);
}

export function createBlogPostId(): string {
  return `blog-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}
