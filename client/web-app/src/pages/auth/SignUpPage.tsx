import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { User, Mail, Lock, ArrowRight, Eye, EyeOff } from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';
import { useTranslation } from '../../i18n/useTranslation';
import { Button } from '../../components/ui/Button';
import { GoogleAuthButton } from '../../components/auth/GoogleAuthButton';
import { ApiError } from '../../lib/apiClient';

export const SignUpPage: React.FC = () => {
  const { t } = useTranslation();
  const { signUp } = useAuthStore();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const passwordValid = password.length >= 8;
  const passwordsMatch = password.length > 0 && password === confirmPassword;
  const canSubmit = passwordValid && passwordsMatch;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !email.trim() || !password) {
      setError(t.auth.requiredFieldError);
      return;
    }
    if (password.length < 8) {
      setError(t.auth.passwordTooShortError);
      return;
    }
    if (password !== confirmPassword) {
      setError(t.auth.passwordMatchError);
      return;
    }
    if (!agreeTerms) {
      setError(t.auth.agreeTermsError);
      return;
    }

    setError('');
    setLoading(true);

    try {
      await signUp(fullName, email, password, 'participant');
      navigate('/onboarding');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(t.auth.emailTaken);
      } else {
        setError(t.auth.signUpFailed);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1.5">
        <h1 className="font-heading text-3xl font-semibold text-ink-900 dark:text-white tracking-tight">
          {t.auth.signUpTitle}
        </h1>
        <p className="text-sm text-ink-500 dark:text-[#8B98AB]">
          {t.auth.signUpSubtitle}
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
            {t.auth.fullNameLabel}
          </label>
          <div className="relative">
            <User className="w-4 h-4 text-[#5A6A85] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Alex Nguyen"
              className="w-full pl-9 pr-3 py-2.5 text-sm rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2563A6] transition-all"
              required
            />
          </div>
        </div>

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

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-[#0F1F38] dark:text-slate-300 mb-1.5">
              {t.auth.passwordLabel}
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-[#5A6A85] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                minLength={8}
                className="w-full pl-9 pr-9 py-2.5 text-sm rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2563A6] transition-all"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#5A6A85] hover:text-[#2563A6]"
                aria-label={showPassword ? t.auth.hidePassword : t.auth.showPassword}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#0F1F38] dark:text-slate-300 mb-1.5">
              {t.auth.confirmPasswordLabel}
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-[#5A6A85] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-9 py-2.5 text-sm rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2563A6] transition-all"
                required
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword((prev) => !prev)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#5A6A85] hover:text-[#2563A6]"
                aria-label={showConfirmPassword ? t.auth.hidePassword : t.auth.showPassword}
              >
                {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>

        <label className="flex items-start gap-2 cursor-pointer text-xs text-[#5A6A85] dark:text-slate-300 pt-1">
          <input
            type="checkbox"
            checked={agreeTerms}
            onChange={(e) => setAgreeTerms(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-[#D5DDEB] accent-[#2563A6] focus:outline-none focus:ring-2 focus:ring-[#2563A6] focus:ring-offset-1"
          />
          {/* Điều khoản phải BẤM ĐƯỢC. Trước đây chỉ là chữ, người dùng
              được yêu cầu đồng ý với một tài liệu họ không có cách nào đọc.
              target="_blank" để không mất dữ liệu form đang nhập dở. */}
          <span>
            {t.auth.agreeToTermsPrefix}
            <Link
              to="/policy"
              target="_blank"
              rel="noreferrer"
              className="font-semibold underline underline-offset-2 hover:text-[#2563A6]"
              onClick={(event) => event.stopPropagation()}
            >
              {t.auth.termsOfService}
            </Link>
            {t.auth.agreeToTermsJoin}
            <Link
              to="/policy"
              target="_blank"
              rel="noreferrer"
              className="font-semibold underline underline-offset-2 hover:text-[#2563A6]"
              onClick={(event) => event.stopPropagation()}
            >
              {t.auth.privacyPolicy}
            </Link>
            {t.auth.agreeToTermsSuffix}
          </span>
        </label>

        <Button
          type="submit"
          disabled={loading || !canSubmit}
          className="w-full py-2.5 bg-[#2563A6] text-white hover:bg-[#1E4E85] font-semibold rounded-xl flex items-center justify-center gap-2"
        >
          <span>{t.actions.signUp}</span>
          <ArrowRight className="w-4 h-4" />
        </Button>
      </form>

      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-[#D5DDEB] dark:bg-[#1A2A42]" />
        <span className="text-xs text-[#5A6A85] dark:text-slate-400 uppercase">{t.auth.orDivider}</span>
        <div className="h-px flex-1 bg-[#D5DDEB] dark:bg-[#1A2A42]" />
      </div>

      <GoogleAuthButton />

      <div className="text-center text-xs text-[#5A6A85]">
        {t.auth.hasAccountQuestion}{' '}
        <Link to="/sign-in" className="text-[#2563A6] font-semibold hover:underline">
          {t.actions.signIn}
        </Link>
      </div>
    </div>
  );
};
