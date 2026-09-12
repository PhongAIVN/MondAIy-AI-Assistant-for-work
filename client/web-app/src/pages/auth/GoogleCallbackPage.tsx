import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { LoaderCircle } from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { useTranslation } from '../../i18n/useTranslation';
import * as authApi from '../../lib/authApi';

/** Đích redirect của /api/v1/auth/google/login — đọc code (đổi lấy token thật
 * qua POST) hoặc status=error từ query, không tự xử lý gì khác. */
export const GoogleCallbackPage: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { signInWithTokens } = useAuthStore();
  const [error, setError] = useState<string | null>(null);
  // StrictMode/HMR gọi effect 2 lần — login code chỉ dùng được 1 lần (60s),
  // lần gọi thứ 2 sẽ 400. Chặn tại đây thay vì dựa vào lỗi từ server.
  const exchanged = useRef(false);

  useEffect(() => {
    if (exchanged.current) return;
    exchanged.current = true;

    const status = searchParams.get('status');
    const code = searchParams.get('code');

    if (status !== 'login_success' || !code) {
      setError(t.auth.googleAuthFailed);
      return;
    }

    authApi
      .exchangeGoogleLoginCode(code)
      .then((tokens) => {
        signInWithTokens(tokens);
        const onboardingDone = usePreferencesStore.getState().onboardingDismissed;
        navigate(onboardingDone ? '/briefing' : '/onboarding', { replace: true });
      })
      .catch(() => setError(t.auth.googleAuthFailed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="text-center space-y-4">
        <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
        <Link to="/sign-in" className="text-sm font-semibold text-[#2563A6] hover:underline">
          {t.actions.signIn}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8 text-sm text-[#5A6A85] dark:text-slate-300">
      <LoaderCircle className="w-5 h-5 animate-spin text-[#2563A6]" />
      <span>{t.auth.googleAuthProcessing}</span>
    </div>
  );
};
