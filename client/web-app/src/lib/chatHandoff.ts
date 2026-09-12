export type ChatHandoffState = {
  chatPrompt: string;
  chatImageFile?: File;
};

export function createChatHandoff(prompt: string): ChatHandoffState {
  const chatPrompt = prompt.trim();
  if (!chatPrompt) throw new Error('Chat handoff requires a non-empty prompt.');
  return { chatPrompt };
}

export function createChatImageHandoff(file: File): ChatHandoffState {
  if (!file.type.startsWith('image/')) throw new Error('Chat image handoff requires an image file.');
  return { chatPrompt: '', chatImageFile: file };
}

export function readChatHandoff(state: unknown): string | null {
  if (!state || typeof state !== 'object' || !('chatPrompt' in state)) return null;
  const prompt = (state as { chatPrompt?: unknown }).chatPrompt;
  if (typeof prompt !== 'string') return null;
  const normalized = prompt.trim();
  return normalized || null;
}

export function readChatImageHandoff(state: unknown): File | null {
  if (!state || typeof state !== 'object' || !('chatImageFile' in state)) return null;
  const file = (state as { chatImageFile?: unknown }).chatImageFile;
  if (typeof File === 'undefined' || !(file instanceof File) || !file.type.startsWith('image/')) return null;
  return file;
}
