import { apiRequest } from './apiClient';

export type Project = {
  id: number;
  name: string;
  description: string;
  color: string;
  conversationCount: number;
  createdAt: string;
  updatedAt: string;
};

export type ProjectSuggestion = {
  projectId: number;
  projectName: string;
  score: number;
  /** 'semantic' khi so bằng vector, 'keyword' khi lùi về khớp từ khoá. */
  method: string;
};

export async function listProjects(accessToken: string): Promise<Project[]> {
  const data = await apiRequest<{ projects: Project[] }>('/api/v1/projects', { accessToken });
  return data.projects;
}

export async function createProject(
  accessToken: string,
  body: { name: string; description?: string; color?: string },
): Promise<Project> {
  return apiRequest<Project>('/api/v1/projects', { method: 'POST', accessToken, body });
}

export async function updateProject(
  accessToken: string,
  projectId: number,
  body: { name?: string; description?: string; color?: string },
): Promise<Project> {
  return apiRequest<Project>(`/api/v1/projects/${projectId}`, { method: 'PATCH', accessToken, body });
}

export async function deleteProject(accessToken: string, projectId: number): Promise<void> {
  await apiRequest<void>(`/api/v1/projects/${projectId}`, { method: 'DELETE', accessToken });
}

export async function addConversationToProject(
  accessToken: string,
  projectId: number,
  conversationId: number,
): Promise<Project> {
  return apiRequest<Project>(`/api/v1/projects/${projectId}/conversations/${conversationId}`, {
    method: 'POST',
    accessToken,
  });
}

export async function removeConversationFromProject(
  accessToken: string,
  conversationId: number,
): Promise<void> {
  await apiRequest<void>(`/api/v1/projects/conversations/${conversationId}`, {
    method: 'DELETE',
    accessToken,
  });
}

/**
 * Dự án khớp nhất cho một hội thoại, hoặc null khi không đủ chắc.
 *
 * Không bao giờ ném lỗi: đây là tiện ích phụ trên màn hình chat, hỏng nó không
 * được chắn đường người dùng đang trò chuyện.
 */
export async function fetchProjectSuggestion(
  accessToken: string,
  conversationId: number,
): Promise<ProjectSuggestion | null> {
  try {
    const data = await apiRequest<{ suggestion: ProjectSuggestion | null }>(
      `/api/v1/projects/suggestion/${conversationId}`,
      { accessToken, timeoutMs: 8000 },
    );
    return data.suggestion;
  } catch {
    return null;
  }
}

export type ProjectConversation = {
  id: number;
  title: string;
  messageCount: number;
  updatedAt: string;
};

export type ProjectMeeting = {
  id: number;
  title: string;
  status: 'open' | 'summarized';
  startedAt: string;
  endedAt: string | null;
  updatedAt: string;
};

export type ProjectOverview = {
  project: Project;
  conversations: ProjectConversation[];
  meetings: ProjectMeeting[];
  meetingCount: number;
  /** Rỗng là hợp lệ — dự án chưa có hội thoại nào. */
  summary: string;
  summaryUpdatedAt: string | null;
};

/**
 * Hội thoại trong dự án + tóm tắt điểm chung.
 *
 * Tóm tắt có cache phía server, khoá bằng dấu vân tay tập hội thoại, nên mở lại
 * trang không tốn thêm lượt gọi LLM. `refresh` ép sinh lại — chỉ dùng khi người
 * dùng tự bấm, không gọi tự động.
 */
export async function fetchProjectOverview(
  accessToken: string,
  projectId: number,
  options: { refresh?: boolean; language?: string } = {},
): Promise<ProjectOverview> {
  const params = new URLSearchParams();
  if (options.refresh) params.set('refresh', 'true');
  if (options.language) params.set('language', options.language);
  const query = params.toString();
  return apiRequest<ProjectOverview>(
    `/api/v1/projects/${projectId}/overview${query ? `?${query}` : ''}`,
    // Sinh tóm tắt có thể gọi LLM — rộng tay hơn mặc định, nhưng vẫn có trần để
    // trang không treo vô hạn khi model chậm.
    { accessToken, timeoutMs: 45000 },
  );
}
