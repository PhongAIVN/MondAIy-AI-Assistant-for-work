// Client admin blog — MinIO khi có, local disk khi chưa, publish mock.

import { API_BASE_URL, apiRequest } from './apiClient';

export type BlogStorageStatus = {
  available: boolean;
  mode: 'live' | 'local' | 'mock' | string;
  endpoint: string;
  bucket: string;
  detail: string | null;
};

export type BlogPresignAsset = {
  objectKey: string;
  url: string;
  expiresIn: number;
  storageMode: string;
};

export type BlogPostDto = {
  id: string;
  slug: string;
  title: string;
  titleVi: string;
  excerpt: string;
  excerptVi: string;
  body: string;
  bodyVi: string;
  author: string;
  tags: string[];
  publishedAt: string;
  status: string;
  coverObjectKey: string | null;
  assetObjectKeys: string[];
  storageMode: string;
  publicPath: string;
};

export type BlogPublishInput = {
  slug: string;
  title: string;
  titleVi: string;
  excerpt: string;
  excerptVi: string;
  body: string;
  bodyVi: string;
  author: string;
  tags: string[];
  coverObjectKey?: string | null;
  assetObjectKeys?: string[];
  markdownSourceName?: string | null;
};

/** URL xem asset local (hoặc absolute path nếu đã là http). */
export function blogAssetPublicUrl(objectKey: string): string {
  if (objectKey.startsWith('http://') || objectKey.startsWith('https://')) {
    return objectKey;
  }
  return `${API_BASE_URL}/api/v1/blog/assets/${objectKey}`;
}

export async function getBlogStorageStatus(accessToken: string): Promise<BlogStorageStatus> {
  return apiRequest<BlogStorageStatus>('/api/v1/admin/blog/storage-status', { accessToken });
}

export async function parseBlogMarkdown(
  accessToken: string,
  markdown: string,
  filename?: string,
): Promise<{
  title: string;
  titleVi: string;
  slug: string;
  author: string;
  excerpt: string;
  excerptVi: string;
  tags: string[];
  body: string;
  bodyVi: string;
}> {
  return apiRequest('/api/v1/admin/blog/parse-markdown', {
    method: 'POST',
    accessToken,
    body: { markdown, filename },
  });
}

export async function presignBlogAsset(
  accessToken: string,
  filename: string,
  contentType: string,
): Promise<BlogPresignAsset> {
  return apiRequest<BlogPresignAsset>('/api/v1/admin/blog/presign-asset', {
    method: 'POST',
    accessToken,
    body: { filename, contentType },
  });
}

/** Upload lên MinIO (live) hoặc PUT vào backend local-upload. */
export async function uploadBlogAsset(
  accessToken: string,
  file: File,
): Promise<BlogPresignAsset & { uploaded: boolean; publicUrl?: string }> {
  const presign = await presignBlogAsset(
    accessToken,
    file.name,
    file.type || 'application/octet-stream',
  );

  if (presign.storageMode === 'local' || presign.url.includes('/admin/blog/local-upload/')) {
    const put = await fetch(presign.url, {
      method: 'PUT',
      headers: {
        'Content-Type': file.type || 'application/octet-stream',
        Authorization: `Bearer ${accessToken}`,
      },
      body: file,
    });
    if (!put.ok) {
      throw new Error(`Upload local thất bại (${put.status})`);
    }
    return {
      ...presign,
      uploaded: true,
      publicUrl: blogAssetPublicUrl(presign.objectKey),
    };
  }

  if (presign.url.startsWith('mock://')) {
    await new Promise((r) => setTimeout(r, 200));
    return { ...presign, uploaded: true };
  }

  const put = await fetch(presign.url, {
    method: 'PUT',
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    body: file,
  });
  if (!put.ok) {
    throw new Error(`Upload MinIO thất bại (${put.status})`);
  }
  return { ...presign, uploaded: true };
}

export async function publishBlogPost(
  accessToken: string,
  payload: BlogPublishInput,
): Promise<BlogPostDto> {
  return apiRequest<BlogPostDto>('/api/v1/admin/blog/posts', {
    method: 'POST',
    accessToken,
    body: payload,
  });
}

export async function listAdminBlogPosts(accessToken: string): Promise<{
  items: BlogPostDto[];
  total: number;
  storageMode: string;
}> {
  return apiRequest('/api/v1/admin/blog/posts', { accessToken });
}

export async function listPublicMockBlogPosts(): Promise<{
  items: BlogPostDto[];
  total: number;
}> {
  return apiRequest('/api/v1/blog/posts');
}
