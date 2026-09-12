import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff, Lock, Mail, ArrowRight, KeyRound } from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { useTranslation } from '../../i18n/useTranslation';
import { Button } from '../../components/ui/Button';
import { GoogleAuthButton } from '../../components/auth/GoogleAuthButton';
import { ApiError } from '../../lib/apiClient';

// Tài khoản demo cho ban giám khảo truy cập nhanh, không cần nhớ mật khẩu.
const DEMO_EMAIL = 'hoaianthai345@gmail.com';
const DEMO_PASSWORD = '12345678';

export const SignInPage: React.FC = () => {
  const { t } = useTranslation();
  const { signIn } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const fromLocation = (location.state as { from?: { pathname?: string; search?: string } } | null)?.from;
  const from = fromLocation?.pathname
    ? `${fromLocation.pathname}${fromLocation.search || ''}`
    : '/briefing';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const doSignIn = async (signInEmail: string, signInPassword: string) => {
    setError('');
    setLoading(true);

    try {
      await signIn(signInEmail, signInPassword, rememberMe);
      const onboardingDone = usePreferencesStore.getState().onboardingDismissed;
      if (!onboardingDone) {
        navigate('/onboarding', { replace: true, state: { returnTo: from } });
        return;
      }
      const target = from === '/sign-in' || from === '/onboarding' ? '/briefing' : from;
      navigate(target);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 404)) {
        setError(t.auth.invalidCredentials);
      } else {
        setError(t.auth.signInFailed);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError(t.auth.requiredFieldError);
      return;
    }
    await doSignIn(email, password);
  };

  const handleDemoLogin = async () => {
    setEmail(DEMO_EMAIL);
    setPassword(DEMO_PASSWORD);
    await doSignIn(DEMO_EMAIL, DEMO_PASSWORD);
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1.5">
        <h1 className="font-heading text-3xl font-semibold text-ink-900 dark:text-white tracking-tight">
          {t.auth.welcomeBack}
        </h1>
        <p className="text-sm text-ink-500 dark:text-[#8B98AB]">
          {t.auth.signInSubtitle}
        </p>
      </div>

      {error && (
        <div className="p-3 text-xs rounded-xl bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-[#0F1F38] dark:text-slate-300 mb-1.5">
            {t.auth.emailLabel}
          </label>
          <div className="relative">
            <Mail className="w-4 h-4 text-[#5A6A85] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alex.nguyen@example.com"
              className="w-full pl-9 pr-3 py-2.5 text-sm rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2563A6] transition-all"
              required
            />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-xs font-semibold text-[#0F1F38] dark:text-slate-300">
              {t.auth.passwordLabel}
            </label>
            <Link
              to="/forgot-password"
              className="text-xs text-[#2563A6] hover:underline font-medium"
            >
              {t.auth.forgotPasswordQuestion}
            </Link>
          </div>
          <div className="relative">
            <Lock className="w-4 h-4 text-[#5A6A85] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full pl-9 pr-9 py-2.5 text-sm rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2563A6] transition-all"
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#5A6A85] hover:text-[#2563A6]"
              aria-label={showPassword ? t.auth.hidePassword : t.auth.showPassword}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 cursor-pointer text-xs text-[#5A6A85] dark:text-slate-300">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="h-4 w-4 shrink-0 cursor-pointer rounded border-[#D5DDEB] accent-[#2563A6] focus:outline-none focus:ring-2 focus:ring-[#2563A6] focus:ring-offset-1"
            />
            <span>{t.auth.rememberMe}</span>
          </label>
        </div>

        <Button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 bg-[#2563A6] text-white hover:bg-[#1E4E85] font-semibold rounded-xl flex items-center justify-center gap-2"
        >
          <span>{t.actions.signIn}</span>
          <ArrowRight className="w-4 h-4" />
        </Button>
      </form>

      <Button
        type="button"
        onClick={handleDemoLogin}
        disabled={loading}
        className="w-full py-2.5 bg-white dark:bg-transparent border border-[#2563A6] text-[#2563A6] hover:bg-[#2563A6]/10 font-semibold rounded-xl flex items-center justify-center gap-2"
      >
        <KeyRound className="w-4 h-4" />
        <span>{t.auth.demoLoginButton}</span>
      </Button>

      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-[#D5DDEB] dark:bg-[#1A2A42]" />
        <span className="text-xs text-[#5A6A85] dark:text-slate-400 uppercase">{t.auth.orDivider}</span>
        <div className="h-px flex-1 bg-[#D5DDEB] dark:bg-[#1A2A42]" />
      </div>

      <GoogleAuthButton />

      <div className="text-center text-xs text-[#5A6A85]">
        {t.auth.noAccountQuestion}{' '}
        <Link to="/sign-up" className="text-[#2563A6] font-semibold hover:underline">
          {t.actions.signUp}
        </Link>
      </div>

      {/* Điều khoản/quyền riêng tư phải với tới được từ CẢ trang đăng nhập,
          không chỉ trang đăng ký: người dùng cũ muốn đọc lại chính sách không
          có lý do gì phải tạo tài khoản mới mới thấy link. */}
      <div className="text-center text-[11px] text-[#5A6A85] dark:text-slate-400">
        <Link to="/policy" target="_blank" rel="noreferrer" className="hover:underline">
          {t.auth.termsOfService}
        </Link>
        <span className="px-1.5">·</span>
        <Link to="/policy" target="_blank" rel="noreferrer" className="hover:underline">
          {t.auth.privacyPolicy}
        </Link>
      </div>
    </div>
  );
};
