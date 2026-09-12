import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';
import { useTranslation } from '../../i18n/useTranslation';
import { Button } from '../../components/ui/Button';

export const ForgotPasswordPage: React.FC = () => {
  const { t } = useTranslation();
  const { forgotPassword } = useAuthStore();

  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    try {
      await forgotPassword(email);
    } catch {
      // Vẫn báo thành công dù lỗi mạng/server — không lộ email nào tồn tại
      // qua khác biệt hành vi giữa "gửi được" và "lỗi".
    } finally {
      setLoading(false);
      setSubmitted(true);
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1.5">
        <h1 className="font-heading text-3xl font-semibold text-ink-900 dark:text-white tracking-tight">
          {t.auth.forgotPasswordTitle}
        </h1>
        <p className="text-sm text-ink-500 dark:text-[#8B98AB]">
          {t.auth.forgotPasswordDesc}
        </p>
      </div>

      {submitted ? (
        <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 space-y-3 text-center">
          <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
          <p className="text-xs leading-relaxed font-medium">
            {t.auth.resetSuccessMessage}
          </p>
          <div className="pt-2">
            <Link
              to="/sign-in"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#2563A6] hover:underline"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> {t.actions.backToSignIn}
            </Link>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
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

          <Button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-[#2563A6] text-white hover:bg-[#1E4E85] font-semibold rounded-xl"
          >
            {t.auth.sendResetInstructions}
          </Button>

          <div className="text-center pt-2">
            <Link
              to="/sign-in"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#5A6A85] hover:text-[#2563A6]"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> {t.actions.backToSignIn}
            </Link>
          </div>
        </form>
      )}
    </div>
  );
};
