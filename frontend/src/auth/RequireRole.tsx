import React from 'react';
import { Navigate, useLocation, Outlet } from 'react-router-dom';
import { useAuth } from './AuthProvider';
import type { UserRole } from '../api/schema';
import { COPY } from '../lib/copy';

interface RequireRoleProps {
  allowedRoles?: UserRole[];
  children?: React.ReactNode;
}

export const RequireRole: React.FC<RequireRoleProps> = ({ allowedRoles, children }) => {
  const { user, role, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div
        className="flex min-h-[300px] items-center justify-center p-8"
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        <div className="flex flex-col items-center gap-3 text-gov-blue">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-gov-blue border-t-transparent" />
          <span className="text-sm font-medium">{COPY.common.loading}</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && allowedRoles.length > 0 && (!role || !allowedRoles.includes(role))) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children ? <>{children}</> : <Outlet />;
};
