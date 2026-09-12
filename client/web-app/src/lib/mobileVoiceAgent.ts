import type { AgentStreamReply } from './agentStream';

export type AgentAudioCue = 'calendar-created' | 'review-required' | 'draft-ready' | 'summary-ready';

type SpeechRecognitionAlternativeLike = { transcript: string };
type SpeechRecognitionResultLike = {
  isFinal: boolean;
  0?: SpeechRecognitionAlternativeLike;
};

export interface BrowserSpeechRecognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: { resultIndex: number; results: ArrayLike<SpeechRecognitionResultLike> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort?: () => void;
}

export type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

const AUDIO_CUE_SETTING_KEY = 'mondaiy.mobileAgentAudioCuesEnabled';

/** Web Speech không có mặt ở mọi trình duyệt, nên luôn phải feature-detect. */
export function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === 'undefined') return null;
  const browserWindow = window as typeof window & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition ?? null;
}

export function isMobileViewport(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(max-width: 767px)').matches === true;
}

export function readMobileAudioCueSetting(): boolean {
  try {
    return localStorage.getItem(AUDIO_CUE_SETTING_KEY) === 'true';
  } catch {
    return false;
  }
}

export function writeMobileAudioCueSetting(enabled: boolean): void {
  try {
    localStorage.setItem(AUDIO_CUE_SETTING_KEY, String(enabled));
  } catch {
    // Private mode có thể chặn localStorage; UI hiện tại vẫn giữ lựa chọn.
  }
}

/** Chỉ suy ra cue từ trạng thái có cấu trúc do server trả về, không đọc văn xuôi. */
export function selectAgentAudioCue(reply: AgentStreamReply): AgentAudioCue {
  if (reply.productivityAction?.status === 'created' && reply.productivityAction.kind === 'calendar_event') {
    return 'calendar-created';
  }
  if (reply.productivityAction?.status === 'pending_approval' || reply.productivityAction?.status === 'needs_clarification') {
    return 'review-required';
  }
  if (reply.taskDrafts.length > 0 || reply.taskSuggestions.length > 0) return 'draft-ready';
  return 'summary-ready';
}

export function agentAudioCueSource(cue: AgentAudioCue, language: 'vi' | 'en'): string {
  return `/audio/agent-${cue}-${language}.mp3`;
}

/** Audio là asset cục bộ; autoplay bị chặn hoặc lỗi codec không được làm hỏng chat. */
export async function playLocalAgentCue(
  cue: AgentAudioCue,
  language: 'vi' | 'en',
  onStart?: (audio: HTMLAudioElement) => void,
): Promise<boolean> {
  if (typeof Audio === 'undefined') return false;
  try {
    const audio = new Audio(agentAudioCueSource(cue, language));
    onStart?.(audio);
    await audio.play();
    return true;
  } catch {
    return false;
  }
}
