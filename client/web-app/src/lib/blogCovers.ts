import coverForest from '../assets/icm-green-forest.webp';
import coverLake from '../assets/icm-lake-reflection.webp';
import coverPath from '../assets/icm-forest-path.webp';
import coverCanopy from '../assets/icm-canopy.webp';
import coverGrass from '../assets/icm-water-grass.webp';
import type { BlogPost } from '../data/blogPosts';
import { blogAssetPublicUrl } from './adminBlogApi';

const FALLBACK_COVERS = [coverForest, coverLake, coverPath, coverCanopy, coverGrass];

/** Ảnh nền card: cover thật nếu có; không thì caller tự dùng gradient. */
export function resolveBlogCoverUrl(post: BlogPost, index = 0): string {
  if (post.coverImageUrl) return post.coverImageUrl;
  return FALLBACK_COVERS[index % FALLBACK_COVERS.length];
}

export function coverUrlFromObjectKey(objectKey: string | null | undefined): string | null {
  if (!objectKey) return null;
  if (objectKey.startsWith('http://') || objectKey.startsWith('https://') || objectKey.startsWith('/')) {
    return objectKey;
  }
  if (objectKey.startsWith('blog/local/')) {
    return blogAssetPublicUrl(objectKey);
  }
  // MinIO key chưa có public URL ổn định trong mock — bỏ qua.
  return null;
}
