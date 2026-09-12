import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Lock, CheckCircle2 } from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';
import { useTranslation } from '../../i18n/useTranslation';
import { Button } from '../../components/ui/Button';

export const ResetPasswordPage: React.FC = () => {
  const { t } = useTranslation();
  const { resetPassword } = useAuthStore();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError(t.auth.resetLinkInvalidError);
      return;
    }
    if (!password) {
      setError(t.auth.requiredFieldError);
      return;
    }
    if (password !== confirmPassword) {
      setError(t.auth.passwordMatchError);
      return;
    }

    setError('');
    setLoading(true);
    try {
      await resetPassword(token, password);
      setSuccess(true);
    } catch {
      // Token sai/hết hạn hay lỗi server đều hiện cùng thông điệp — người
      // dùng chỉ cần biết là xin link mới, không cần phân biệt nguyên nhân.
      setError(t.auth.resetLinkInvalidError);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1.5">
        <h1 className="font-heading text-3xl font-semibold text-ink-900 dark:text-white tracking-tight">
          {t.auth.resetPasswordTitle}
        </h1>
        <p className="text-sm text-[#5A6A85] dark:text-[#8B98AB]">
          {t.auth.resetPasswordDesc}
        </p>
      </div>

      {error && (
        <div className="p-3 text-xs rounded-xl bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900">
          {error}
        </div>
      )}

      {success ? (
        <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 space-y-3 text-center">
          <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
          <p className="text-xs leading-relaxed font-medium">
            {t.auth.passwordUpdatedSuccess}
          </p>
          <div className="pt-2">
            <Link
              to="/sign-in"
              className="inline-block px-4 py-2 bg-[#2563A6] text-white text-xs font-semibold rounded-xl hover:bg-[#1E4E85]"
            >
              {t.actions.signIn}
            </Link>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[#0F1F38] dark:text-slate-300 mb-1.5">
              {t.auth.passwordLabel}
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-[#5A6A85] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-3 py-2.5 text-sm rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2563A6] transition-all"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#0F1F38] dark:text-slate-300 mb-1.5">
              {t.auth.confirmPasswordLabel}
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-[#5A6A85] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-3 py-2.5 text-sm rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2563A6] transition-all"
                required
              />
            </div>
          </div>

          <Button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-[#2563A6] text-white hover:bg-[#1E4E85] font-semibold rounded-xl"
          >
            {t.auth.updatePasswordAction}
          </Button>
        </form>
      )}
    </div>
  );
};
