/**
 * Tương thích ngược: API cũ redirect sang managedBlogCatalog.
 */

import type { BlogPost } from '../data/blogPosts';
import type { BlogPostDto } from './adminBlogApi';
import { coverUrlFromObjectKey } from './blogCovers';
import {
  getManagedBlogPostBySlug,
  listManagedBlogPosts,
  upsertManagedBlogPost,
} from './managedBlogCatalog';

export function dtoToBlogPost(dto: BlogPostDto): BlogPost {
  return {
    id: dto.id,
    slug: dto.slug,
    title: dto.title,
    titleVi: dto.titleVi || dto.title,
    excerpt: dto.excerpt,
    excerptVi: dto.excerptVi || dto.excerpt,
    body: dto.body,
    bodyVi: dto.bodyVi || dto.body,
    author: dto.author,
    publishedAt: dto.publishedAt,
    tags: dto.tags,
    coverImageUrl: coverUrlFromObjectKey(dto.coverObjectKey),
  };
}

export function listLocalPublishedPosts(): BlogPost[] {
  return listManagedBlogPosts();
}

export function getLocalPublishedPost(slug: string): BlogPost | null {
  return getManagedBlogPostBySlug(slug);
}

export function saveLocalPublishedPost(post: BlogPost): void {
  upsertManagedBlogPost(post);
}

export function saveLocalPublishedFromDto(dto: BlogPostDto): BlogPost {
  const post = dtoToBlogPost(dto);
  upsertManagedBlogPost(post);
  return post;
}

export function publishLocalOnly(input: {
  slug: string;
  title: string;
  titleVi: string;
  excerpt: string;
  excerptVi: string;
  body: string;
  bodyVi: string;
  author: string;
  tags: string[];
  coverImageUrl?: string | null;
}): BlogPost {
  const post: BlogPost = {
    id: `local-${Date.now().toString(36)}`,
    slug: input.slug,
    title: input.title,
    titleVi: input.titleVi || input.title,
    excerpt: input.excerpt,
    excerptVi: input.excerptVi || input.excerpt,
    body: input.body,
    bodyVi: input.bodyVi || input.body,
    author: input.author,
    publishedAt: new Date().toISOString().slice(0, 10),
    tags: input.tags,
    coverImageUrl: input.coverImageUrl ?? null,
  };
  upsertManagedBlogPost(post);
  return post;
}
