import type { FC } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './auth-context';
import { LoadingState } from '../components/LoadingState';

export const ProtectedRoute: FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--color-bg)',
        }}
      >
        <LoadingState label="VERIFYING CREDENTIALS..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
};
