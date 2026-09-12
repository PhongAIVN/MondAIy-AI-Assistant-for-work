import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { useMotionEnabled } from '../../hooks/useMotionEnabled';

const THINKING_DELAY_MS = 500;
/** Giả lập cảm giác đang gõ trả lời thật thay vì dán nguyên câu ra ngay. */
const REVEAL_WORD_MS = 45;
const PAUSE_BEFORE_QUESTION_MS = 600;
const READ_PAUSE_MS = 1700;
const CYCLE_RESET_PAUSE_MS = 500;

interface DisplayMessage {
  role: 'user' | 'assistant';
  text: string;
}

interface TryChatPageProps {
  embedded?: boolean;
}

/**
 * Demo tự chạy (không cho gõ) — bản cũ cho nhập tự do và gọi public-ask thật,
 * hỏi ngoài luồng FAQ thì lặp lại đúng câu fallback nhiều lần trông như kẹt
 * vòng lặp. Giờ chỉ diễn lại kịch bản 3 câu hỏi/đáp cố định, an toàn tuyệt đối.
 */
export const TryChatPage: React.FC<TryChatPageProps> = ({ embedded = false }) => {
  const { t } = useTranslation();
  const motionEnabled = useMotionEnabled();
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [pendingReply, setPendingReply] = useState<string | null>(null);
  // setTimeout bị trình duyệt "throttle" rất mạnh ở tab nền (background tab),
  // không chạy sát thời gian đặt — quay lại tab dễ thấy vòng lặp tăng tốc/kẹt
  // giữa chừng. Tạm dừng hẳn auto-play khi ẩn tab, chạy lại sạch từ đầu khi
  // hiện lại, thay vì cố "đuổi kịp" thời gian đã trôi qua lúc ẩn.
  const [isPageVisible, setIsPageVisible] = useState(
    () => typeof document === 'undefined' || !document.hidden,
  );

  useEffect(() => {
    const handleVisibilityChange = () => setIsPageVisible(!document.hidden);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  const script = useMemo(
    () => [
      { question: t.marketing.tryChatFaqQ1, answer: t.marketing.tryChatFaqA1 },
      { question: t.marketing.tryChatFaqQ2, answer: t.marketing.tryChatFaqA2 },
      { question: t.marketing.tryChatFaqQ3, answer: t.marketing.tryChatFaqA3 },
    ],
    [t],
  );

  useEffect(() => {
    if (!motionEnabled || !isPageVisible) {
      setMessages([]);
      setIsThinking(false);
      setPendingReply(null);
      return undefined;
    }
    let cancelled = false;
    let timeoutId: number | undefined;
    const wait = (ms: number) =>
      new Promise<void>((resolve) => {
        timeoutId = window.setTimeout(resolve, ms);
      });

    const run = async () => {
      let index = 0;
      while (!cancelled) {
        const pair = script[index];

        await wait(PAUSE_BEFORE_QUESTION_MS);
        if (cancelled) return;
        setMessages((prev) => [...prev, { role: 'user', text: pair.question }]);

        await wait(THINKING_DELAY_MS);
        if (cancelled) return;
        setIsThinking(true);

        await wait(THINKING_DELAY_MS);
        if (cancelled) return;
        setIsThinking(false);
        setPendingReply('');

        const words = pair.answer.split(' ');
        for (let count = 1; count <= words.length; count += 1) {
          if (cancelled) return;
          setPendingReply(words.slice(0, count).join(' '));
          await wait(REVEAL_WORD_MS);
        }
        if (cancelled) return;
        setMessages((prev) => [...prev, { role: 'assistant', text: pair.answer }]);
        setPendingReply(null);

        await wait(READ_PAUSE_MS);
        if (cancelled) return;

        index += 1;
        if (index >= script.length) {
          index = 0;
          await wait(CYCLE_RESET_PAUSE_MS);
          if (cancelled) return;
          setMessages([]);
        }
      }
    };

    run();

    return () => {
      cancelled = true;
      if (timeoutId) window.clearTimeout(timeoutId);
    };
  }, [motionEnabled, isPageVisible, script]);

  // Motion tắt (accessibility): không tự chạy vòng lặp, hiện tĩnh 1 lượt hỏi/đáp mẫu.
  const staticPair = script[0];
  const displayMessages: DisplayMessage[] = motionEnabled
    ? messages
    : [
        { role: 'user', text: staticPair.question },
        { role: 'assistant', text: staticPair.answer },
      ];

  // Card chiều cao cố định, cuộn nội bộ — trước đây panel cao dần theo số tin
  // nhắn khiến cả trang landing bị đẩy/giật mỗi khi demo tự phát thêm bong
  // bóng lúc người dùng đang cuộn qua section khác.
  const transcriptRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = transcriptRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [displayMessages, isThinking, pendingReply]);

  return (
    <div className={`mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 ${embedded ? 'py-16 sm:py-20' : 'py-12 sm:py-16'}`}>
      {!embedded && (
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-500 transition-colors hover:text-action-solid"
        >
          <ArrowLeft className="h-4 w-4" strokeWidth={1.5} />
          {t.marketing.blogBackHome}
        </Link>
      )}

      <div className={`${embedded ? '' : 'mt-8'} space-y-1`}>
        <h1 className="text-balance text-[clamp(2.15rem,4vw,3.15rem)] font-semibold leading-[1.12] tracking-[-0.025em] text-ink-900">
          {t.marketing.tryChatTitle}
        </h1>
        <p className="text-sm text-ink-500">{t.marketing.tryChatSubtitle}</p>
      </div>

      <div
        ref={transcriptRef}
        className="mt-8 h-[360px] overflow-y-auto rounded-2xl border border-hairline bg-paper-sunken p-4 sm:p-6"
      >
        <div className="space-y-4">
          {displayMessages.map((msg, index) => (
            <motion.div
              key={`${msg.role}-${index}-${msg.text.slice(0, 16)}`}
              layout
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xl whitespace-pre-line rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-action-solid text-[var(--color-on-primary)]'
                    : 'bg-paper-raised text-ink-900'
                }`}
              >
                {msg.text}
              </div>
            </motion.div>
          ))}

          {isThinking && (
            <motion.div
              key="thinking"
              layout
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start"
            >
              <div className="flex items-center gap-1 rounded-2xl bg-paper-raised px-4 py-2.5">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-400 [animation-delay:-0.2s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-400 [animation-delay:-0.1s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-400" />
              </div>
            </motion.div>
          )}

          {pendingReply !== null && (
            <motion.div
              key="pending"
              layout
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start"
            >
              <div className="max-w-xl whitespace-pre-line rounded-2xl bg-paper-raised px-4 py-2.5 text-sm leading-relaxed text-ink-900">
                {pendingReply}
                <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-ink-400 align-middle" />
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
};
