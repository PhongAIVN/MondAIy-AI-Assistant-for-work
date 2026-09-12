import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/useAuthStore';
import { BootstrapScreen } from './BootstrapScreen';

type GuestRouteProps = {
  children: React.ReactNode;
};

/** Đã có token hợp lệ mà vào /sign-in, /sign-up... thì đưa thẳng về /briefing,
 * không bắt đăng nhập lại. */
export const GuestRoute: React.FC<GuestRouteProps> = ({ children }) => {
  const { isAuthenticated, isBootstrapping, accessToken } = useAuthStore();

  if (isBootstrapping) {
    return <BootstrapScreen />;
  }

  if (isAuthenticated && accessToken) {
    return <Navigate to="/briefing" replace />;
  }

  return <>{children}</>;
};
