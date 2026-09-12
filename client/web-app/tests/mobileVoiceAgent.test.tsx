import { describe, expect, it, vi } from 'vitest';

import {
  agentAudioCueSource,
  getSpeechRecognitionConstructor,
  playLocalAgentCue,
  readMobileAudioCueSetting,
  selectAgentAudioCue,
  writeMobileAudioCueSetting,
} from '../src/lib/mobileVoiceAgent';

describe('mobile voice agent helpers', () => {
  it('selects audio only from structured terminal state, never assistant wording', () => {
    expect(selectAgentAudioCue({
      response: 'Tôi đã thêm vào lịch cho bạn', analysis: '', taskDrafts: [], taskSuggestions: [],
    })).toBe('summary-ready');
    expect(selectAgentAudioCue({
      response: '', analysis: '', taskDrafts: [], taskSuggestions: [],
      productivityAction: { status: 'created', kind: 'calendar_event', message: 'confirmed' },
    })).toBe('calendar-created');
    expect(selectAgentAudioCue({
      response: '', analysis: '', taskDrafts: [], taskSuggestions: [],
      productivityAction: { status: 'pending_approval', kind: 'calendar_event', message: 'review' },
    })).toBe('review-required');
  });

  it('keeps response audio opt-in and persists the setting', () => {
    localStorage.clear();
    expect(readMobileAudioCueSetting()).toBe(false);
    writeMobileAudioCueSetting(true);
    expect(readMobileAudioCueSetting()).toBe(true);
    expect(agentAudioCueSource('summary-ready', 'vi')).toBe('/audio/agent-summary-ready-vi.mp3');
  });

  it('uses browser recognition only when the browser exposes it', () => {
    const original = (window as typeof window & { SpeechRecognition?: unknown }).SpeechRecognition;
    expect(getSpeechRecognitionConstructor()).toBeNull();
    class Recognition { start = vi.fn(); stop = vi.fn(); lang = ''; interimResults = false; continuous = false; onresult = null; onerror = null; onend = null; }
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: Recognition });
    expect(getSpeechRecognitionConstructor()).toBe(Recognition);
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: original });
  });

  it('safely ignores rejected local audio playback', async () => {
    const originalAudio = globalThis.Audio;
    Object.defineProperty(globalThis, 'Audio', { configurable: true, value: class { play = vi.fn().mockRejectedValue(new Error('blocked')); } });
    await expect(playLocalAgentCue('summary-ready', 'en')).resolves.toBe(false);
    Object.defineProperty(globalThis, 'Audio', { configurable: true, value: originalAudio });
  });
});
