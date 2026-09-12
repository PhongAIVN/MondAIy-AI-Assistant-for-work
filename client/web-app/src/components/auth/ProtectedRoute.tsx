import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore, type UserRole } from '../../stores/useAuthStore';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { useAppStore } from '../../stores/useAppStore';
import { useTranslation } from '../../i18n/useTranslation';
import { BootstrapScreen } from './BootstrapScreen';

type ProtectedRouteProps = {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
  /** Bỏ qua bắt buộc onboarding (vd. admin portal). */
  skipOnboardingGate?: boolean;
};

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
  skipOnboardingGate = false,
}) => {
  const { isAuthenticated, isBootstrapping, user, accessToken } = useAuthStore();
  const onboardingDismissed = usePreferencesStore((s) => s.onboardingDismissed);
  const { addToast } = useAppStore();
  const { t } = useTranslation();
  const location = useLocation();

  if (isBootstrapping) {
    return <BootstrapScreen />;
  }

  if (!isAuthenticated || !user || !accessToken) {
    return <Navigate to="/sign-in" state={{ from: location }} replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    addToast({
      type: 'warning',
      title: 'Access Restricted',
      message: t.auth.noPermissionAdmin,
    });
    return <Navigate to="/briefing" replace />;
  }

  const isOnboardingRoute = location.pathname === '/onboarding';
  const mustCompleteOnboarding =
    !skipOnboardingGate && user.role !== 'admin' && !onboardingDismissed;

  if (mustCompleteOnboarding && !isOnboardingRoute) {
    return <Navigate to="/onboarding" replace />;
  }

  // Onboarding đã xong thì khoá luôn URL /onboarding — chỉ admin được vào lại
  // (vd. xem/test lại wizard). Ẩn khỏi nav thôi không đủ, gõ thẳng link vẫn
  // vào được nếu thiếu chặn này.
  const onboardingAlreadyDone = user.role !== 'admin' && onboardingDismissed;
  if (isOnboardingRoute && onboardingAlreadyDone) {
    return <Navigate to="/briefing" replace />;
  }

  return <>{children}</>;
};
