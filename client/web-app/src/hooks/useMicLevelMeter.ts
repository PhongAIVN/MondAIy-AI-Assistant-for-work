import { useEffect, useRef, useState } from 'react';

const BAR_COUNT = 28;
const IDLE_LEVEL = 0.06;

function idleLevels(): number[] {
  return Array(BAR_COUNT).fill(IDLE_LEVEL);
}

/**
 * Đọc mức âm lượng micro theo thời gian thực qua AnalyserNode, tách biệt
 * hoàn toàn với SpeechRecognition (API đó không lộ ra dữ liệu biên độ).
 * Chạm mic thật (getUserMedia) chỉ để vẽ waveform, không ghi/lưu audio.
 */
export function useMicLevelMeter(active: boolean, deviceId?: string | null): number[] {
  const [levels, setLevels] = useState<number[]>(idleLevels);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!active || typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      return;
    }
    let cancelled = false;

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: deviceId ? { deviceId: { exact: deviceId } } : true,
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        const AudioCtxCtor =
          window.AudioContext ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (!AudioCtxCtor) return;
        const audioCtx = new AudioCtxCtor();
        audioCtxRef.current = audioCtx;
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.6;
        source.connect(analyser);
        const data = new Uint8Array(analyser.frequencyBinCount);
        const step = Math.max(1, Math.floor(data.length / BAR_COUNT));

        const tick = () => {
          analyser.getByteFrequencyData(data);
          const next: number[] = [];
          for (let i = 0; i < BAR_COUNT; i += 1) {
            const value = data[i * step] ?? 0;
            next.push(Math.max(IDLE_LEVEL, value / 255));
          }
          setLevels(next);
          rafRef.current = requestAnimationFrame(tick);
        };
        tick();
      } catch {
        // Từ chối quyền micro hoặc thiết bị lỗi — giữ level phẳng, không phá UI.
      }
    };

    void start();

    return () => {
      cancelled = true;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      void audioCtxRef.current?.close();
      audioCtxRef.current = null;
      setLevels(idleLevels());
    };
  }, [active, deviceId]);

  return levels;
}
