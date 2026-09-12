---
title: Testing the Mondaiy blog publish flow
title_vi: Thử luồng đăng bài blog Mondaiy
slug: testing-blog-publish-flow
author: Admin Tester
tags: product, ops
excerpt: A short sample used to exercise markdown upload, local image storage, and mock publish.
excerpt_vi: Bài mẫu để thử upload markdown, lưu ảnh local và đăng mock.
---

# Why this sample exists

Use this file in **Admin → Blog Publishing**:

1. Upload this markdown.
2. Attach any small image (or `sample-cover.png` next to this file).
3. Click **Đăng mock**.
4. Open `/blog/testing-blog-publish-flow`.

## What you should see

- Form fields filled from frontmatter
- Live markdown preview with **bold**, *italic*, and `inline code`
- Image stored under `data/blog-assets/` when MinIO is offline

> Tip: MinIO is optional for this dry-run. Local disk is enough.
