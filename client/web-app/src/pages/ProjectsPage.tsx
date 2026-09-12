import React, { useCallback, useEffect, useRef, useState } from 'react';
import { FolderOpen, Plus, Trash2, Pencil, Check, X, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Button } from '../components/ui/Button';
import { useTranslation } from '../i18n/useTranslation';
import {
  createProject,
  deleteProject,
  listProjects,
  updateProject,
  type Project,
} from '../lib/projectsApi';
import { useAppStore } from '../stores/useAppStore';
import { useAuthStore } from '../stores/useAuthStore';

const COLORS = ['slate', 'jade', 'plum', 'amber', 'rose'] as const;

const SWATCH: Record<string, string> = {
  slate: '#5B6C78',
  jade: '#2F6B4F',
  plum: '#6B3F73',
  amber: '#B07D2B',
  rose: '#A34A5E',
};

export const ProjectsPage: React.FC = () => {
  const { language } = useTranslation();
  const vi = language === 'vi';
  const accessToken = useAuthStore((s) => s.accessToken);
  const navigate = useNavigate();
  const addToast = useAppStore((s) => s.addToast);
  const nameInputRef = useRef<HTMLInputElement>(null);

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState<string>('slate');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');

  const reload = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      setProjects(await listProjects(accessToken));
    } catch (error) {
      addToast({
        type: 'error',
        title: vi ? 'Không tải được dự án' : 'Could not load projects',
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setLoading(false);
    }
  }, [accessToken, addToast, vi]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const handleCreate = async () => {
    if (!accessToken || !name.trim()) return;
    setCreating(true);
    try {
      await createProject(accessToken, { name: name.trim(), description: description.trim(), color });
      setName('');
      setDescription('');
      setColor('slate');
      await reload();
    } catch (error) {
      // 409 = trùng tên. Nói thẳng thay vì để người dùng bấm lại rồi tự đoán.
      const message = error instanceof Error ? error.message : String(error);
      addToast({
        type: 'error',
        title: vi ? 'Không tạo được dự án' : 'Could not create project',
        message: /409|trùng/i.test(message)
          ? vi
            ? 'Bạn đã có dự án trùng tên.'
            : 'You already have a project with that name.'
          : message,
      });
    } finally {
      setCreating(false);
    }
  };

  const handleRename = async (project: Project) => {
    if (!accessToken || !editName.trim()) return;
    try {
      await updateProject(accessToken, project.id, { name: editName.trim() });
      setEditingId(null);
      await reload();
    } catch (error) {
      addToast({
        type: 'error',
        title: vi ? 'Không đổi tên được' : 'Rename failed',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const handleDelete = async (project: Project) => {
    if (!accessToken) return;
    // Nói rõ hội thoại KHÔNG bị xoá — nếu không người dùng sẽ ngại bấm, hoặc
    // bấm rồi tưởng mất trắng lịch sử.
    const confirmed = window.confirm(
      vi
        ? `Xoá dự án “${project.name}”? Các hội thoại bên trong được giữ lại và trở về nhóm chưa xếp.`
        : `Delete project “${project.name}”? Its conversations are kept and return to the unsorted pile.`,
    );
    if (!confirmed) return;
    try {
      await deleteProject(accessToken, project.id);
      await reload();
    } catch (error) {
      addToast({
        type: 'error',
        title: vi ? 'Không xoá được dự án' : 'Could not delete project',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  };

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
      <header className="mb-6">
        <h1 className="font-heading text-3xl text-[var(--color-text-primary)]">
          {vi ? 'Dự án' : 'Projects'}
        </h1>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
          {vi
            ? 'Gom các hội thoại liên quan vào một chỗ. Mondaiy sẽ gợi ý khi thấy hội thoại mới thuộc về dự án nào.'
            : 'Group related conversations. Mondaiy suggests a project when a new conversation looks related.'}
        </p>
      </header>

      <section
        aria-label={vi ? 'Tạo dự án mới' : 'Create a project'}
        className="mb-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
      >
        <h2 className="font-heading text-lg text-[var(--color-text-primary)]">
          {vi ? 'Dự án mới' : 'New project'}
        </h2>
        <div className="mt-3 space-y-2.5">
          <input
            ref={nameInputRef}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={vi ? 'Tên dự án' : 'Project name'}
            aria-label={vi ? 'Tên dự án' : 'Project name'}
            className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
          />
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={2}
            placeholder={
              vi
                ? 'Mô tả ngắn — dùng để nhận ra hội thoại nào thuộc dự án này'
                : 'Short description — used to recognise related conversations'
            }
            aria-label={vi ? 'Mô tả dự án' : 'Project description'}
            className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
          />
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-1.5">
              {COLORS.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setColor(item)}
                  aria-label={item}
                  aria-pressed={color === item}
                  className={`h-5 w-5 rounded-full border-2 transition-transform hover:scale-110 ${
                    color === item ? 'border-[var(--color-primary)] scale-110' : 'border-transparent'
                  }`}
                  style={{ backgroundColor: SWATCH[item] }}
                />
              ))}
            </div>
            <Button
              variant="primary"
              size="sm"
              icon={<Plus className="h-4 w-4" />}
              onClick={handleCreate}
              disabled={creating || !name.trim()}
            >
              {vi ? 'Tạo dự án' : 'Create project'}
            </Button>
          </div>
        </div>
      </section>

      {loading ? (
        <p className="text-sm text-[var(--color-text-secondary)]">{vi ? 'Đang tải…' : 'Loading…'}</p>
      ) : projects.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[var(--color-border)] p-8 text-center">
          <FolderOpen className="mx-auto mb-2 h-7 w-7 text-[var(--color-text-muted)]" />
          <p className="text-sm text-[var(--color-text-secondary)]">
            {vi
              ? 'Chưa có dự án nào. Tạo dự án đầu tiên để gom các hội thoại liên quan.'
              : 'No projects yet. Create your first project to group related conversations.'}
          </p>
          <Button
            variant="primary"
            size="sm"
            icon={<Plus className="h-4 w-4" />}
            onClick={() => nameInputRef.current?.focus()}
            className="mt-4"
          >
            {vi ? 'Tạo dự án đầu tiên' : 'Create first project'}
          </Button>
        </div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {projects.map((project) => (
            <li
              key={project.id}
              className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex min-w-0 items-start gap-2.5">
                  <span
                    className="mt-1 h-3 w-3 shrink-0 rounded-full"
                    style={{ backgroundColor: SWATCH[project.color] || SWATCH.slate }}
                  />
                  <div className="min-w-0">
                    {editingId === project.id ? (
                      <div className="flex items-center gap-1.5">
                        <input
                          value={editName}
                          onChange={(event) => setEditName(event.target.value)}
                          aria-label={vi ? 'Tên dự án' : 'Project name'}
                          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-2 py-1 text-sm"
                        />
                        <button type="button" onClick={() => handleRename(project)} aria-label="save">
                          <Check className="h-4 w-4 text-[var(--color-primary)]" />
                        </button>
                        <button type="button" onClick={() => setEditingId(null)} aria-label="cancel">
                          <X className="h-4 w-4 text-[var(--color-text-muted)]" />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => navigate(`/projects/${project.id}`)}
                        className="block max-w-full truncate text-left font-heading text-base text-[var(--color-text-primary)] hover:underline"
                      >
                        {project.name}
                      </button>
                    )}
                    {project.description ? (
                      <p className="mt-1 line-clamp-2 text-xs text-[var(--color-text-secondary)]">
                        {project.description}
                      </p>
                    ) : null}
                    {/* Mở trang chi tiết thay vì bung tại chỗ: trang đó có
                        thêm cột tổng quan, và giữ cả hai lối là hai đường cho
                        cùng một việc. */}
                    <button
                      type="button"
                      onClick={() => navigate(`/projects/${project.id}`)}
                      className="mt-2 flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
                    >
                      <ChevronRight className="h-3 w-3" />
                      {vi
                        ? `${project.conversationCount} hội thoại`
                        : `${project.conversationCount} conversation${project.conversationCount === 1 ? '' : 's'}`}
                    </button>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingId(project.id);
                      setEditName(project.name);
                    }}
                    aria-label={vi ? 'Đổi tên' : 'Rename'}
                    className="rounded-lg p-1.5 hover:bg-[var(--color-surface-hover)]"
                  >
                    <Pencil className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(project)}
                    aria-label={vi ? 'Xoá dự án' : 'Delete project'}
                    className="rounded-lg p-1.5 hover:bg-[var(--color-surface-hover)]"
                  >
                    <Trash2 className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
                  </button>
                </div>
              </div>

            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
