import type { FC, ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { AppLayout } from '../components/AppLayout';
import { LoginView } from '../features/auth/LoginView';
import { RegisterView } from '../features/auth/RegisterView';
import { LandingPage } from '../features/landing/LandingPage';
import { DashboardView } from '../features/dashboard/DashboardView';
import { AssistantView } from '../features/assistant/AssistantView';
import { InvoicesView } from '../features/invoices/InvoicesView';
import { InvoiceFormView } from '../features/invoices/InvoiceFormView';
import { InvoiceDetailView } from '../features/invoices/InvoiceDetailView';
import { BryntumInvoiceCalendar } from '../features/calendar/BryntumInvoiceCalendar';
import { CustomersView } from '../features/customers/CustomersView';
import { ApprovalsView } from '../features/approvals/ApprovalsView';
import { AnalyticsView } from '../features/analytics/AnalyticsView';
import { SettingsView } from '../features/settings/SettingsView';
import { AuthProvider, useAuth } from '../lib/auth-context';
import { ProtectedRoute } from '../lib/protected-route';

const AuthenticatedLayoutWrapper: FC<{ children: ReactNode }> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  // Extract primary segment for active nav state
  const pathSegment = location.pathname.split('/')[1] || 'dashboard';

  return (
    <AppLayout
      activeNavId={pathSegment}
      onNavigate={(id) => navigate(`/${id}`)}
      userEmail={user?.email}
      onLogout={logout}
      brandSubtitle={user?.business_name ? `${user.business_name.toUpperCase()} // AR AGENT` : undefined}
    >
      {children}
    </AppLayout>
  );
};

export const AppRouter: FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Landing & Marketing */}
          <Route path="/" element={<LandingPage />} />

          {/* Public Authentication Screens */}
          <Route path="/login" element={<LoginView />} />
          <Route path="/register" element={<RegisterView />} />

          {/* Protected Business Operating Screens */}
          <Route element={<ProtectedRoute />}>
            <Route
              path="/dashboard"
              element={
                <AuthenticatedLayoutWrapper>
                  <DashboardView />
                </AuthenticatedLayoutWrapper>
              }
            />
            <Route
              path="/assistant"
              element={
                <AuthenticatedLayoutWrapper>
                  <AssistantView />
                </AuthenticatedLayoutWrapper>
              }
            />
            <Route
              path="/invoices"
              element={
                <AuthenticatedLayoutWrapper>
                  <InvoicesView />
                </AuthenticatedLayoutWrapper>
              }
            />
            <Route
              path="/invoices/new"
              element={
                <AuthenticatedLayoutWrapper>
                  <InvoiceFormView />
                </AuthenticatedLayoutWrapper>
              }
            />
            <Route
              path="/invoices/:id"
              element={
                <AuthenticatedLayoutWrapper>
                  <InvoiceDetailView />
                </AuthenticatedLayoutWrapper>
              }
            />
            <Route
              path="/invoices/:id/edit"
              element={
                <AuthenticatedLayoutWrapper>
                  <InvoiceFormView />
                </AuthenticatedLayoutWrapper>
              }
            />
            <Route
              path="/calendar"
              element={
                <AuthenticatedLayoutWrapper>
                  <BryntumInvoiceCalendar />
                </AuthenticatedLayoutWrapper>
              }
            />
            <Route
              path="/customers"
              element={
                <AuthenticatedLayoutWrapper>
                  <CustomersView />
                </AuthenticatedLayoutWrapper>
              }
            />
            <Route
              path="/approvals"
              element={
                <AuthenticatedLayoutWrapper>
                  <ApprovalsView />
                </AuthenticatedLayoutWrapper>
              }
            />
            <Route
              path="/analytics"
              element={
                <AuthenticatedLayoutWrapper>
                  <AnalyticsView />
                </AuthenticatedLayoutWrapper>
              }
            />
            <Route
              path="/settings"
              element={
                <AuthenticatedLayoutWrapper>
                  <SettingsView />
                </AuthenticatedLayoutWrapper>
              }
            />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};
