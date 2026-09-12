import React, { useState } from 'react';
import { CircleCheck, MessageCircleQuestion } from 'lucide-react';
import { submitProgramInformationRequest } from '../../lib/programInformationApi';

type Props = {
  accessToken: string;
  initialQuestion: string;
  language: 'vi' | 'en';
};

export const ProgramQuestionEscalation: React.FC<Props> = ({
  accessToken,
  initialQuestion,
  language,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [question, setQuestion] = useState(initialQuestion);
  const [hasConsent, setHasConsent] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (submitted) {
    return (
      <p className="inline-flex items-center gap-1.5 text-xs text-[var(--color-success)]" role="status">
        <CircleCheck className="h-4 w-4" />
        {language === 'vi'
          ? 'Đã chuyển câu hỏi cho đội ngũ chương trình.'
          : 'Your question was sent to the program team.'}
      </p>
    );
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-[var(--color-border)] px-3 py-2 text-xs font-semibold text-[var(--color-primary)] hover:bg-[var(--color-accent-soft)]"
      >
        <MessageCircleQuestion className="h-4 w-4" />
        {language === 'vi' ? 'Nhờ đội ngũ chương trình trả lời' : 'Ask the program team'}
      </button>
    );
  }

  const submit = async () => {
    const sharedQuestion = question.trim();
    if (!sharedQuestion || !hasConsent) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await submitProgramInformationRequest(accessToken, sharedQuestion);
      setSubmitted(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="max-w-2xl space-y-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div>
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
          {language === 'vi' ? 'Chuyển đúng câu hỏi cho đội ngũ' : 'Share this question with the team'}
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-[var(--color-text-secondary)]">
          {language === 'vi'
            ? 'Chỉ nội dung trong ô dưới đây được chia sẻ. Lịch sử chat, hồ sơ và memory của bạn không được gửi.'
            : 'Only the text below is shared. Your chat history, profile, and memory are not sent.'}
        </p>
      </div>
      <textarea
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        rows={3}
        maxLength={1000}
        aria-label={language === 'vi' ? 'Câu hỏi chia sẻ với đội ngũ' : 'Question shared with the team'}
        className="w-full resize-y rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
      />
      <label className="flex items-start gap-2 text-xs leading-relaxed text-[var(--color-text-secondary)]">
        <input
          type="checkbox"
          checked={hasConsent}
          onChange={(event) => setHasConsent(event.target.checked)}
          className="mt-0.5"
        />
        {language === 'vi'
          ? 'Tôi đồng ý chia sẻ đúng câu hỏi trên với đội ngũ chương trình.'
          : 'I agree to share exactly the question above with the program team.'}
      </label>
      {error && <p role="alert" className="text-xs text-[var(--color-danger)]">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void submit()}
          disabled={!question.trim() || !hasConsent || isSubmitting}
          className="min-h-11 rounded-xl bg-[var(--color-primary)] px-4 py-2 text-xs font-semibold text-[var(--color-on-primary)] disabled:opacity-50"
        >
          {isSubmitting
            ? language === 'vi' ? 'Đang gửi…' : 'Sending…'
            : language === 'vi' ? 'Xác nhận gửi' : 'Confirm and send'}
        </button>
        <button
          type="button"
          onClick={() => setIsOpen(false)}
          disabled={isSubmitting}
          className="min-h-11 rounded-xl border border-[var(--color-border)] px-4 py-2 text-xs font-semibold text-[var(--color-text-secondary)]"
        >
          {language === 'vi' ? 'Huỷ' : 'Cancel'}
        </button>
      </div>
    </section>
  );
};
