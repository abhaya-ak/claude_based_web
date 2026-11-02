import { createBrowserRouter } from 'react-router-dom';
import { PublicLayout } from './layout/PublicLayout';
import { StaffLayout } from './layout/StaffLayout';
import { RequireRole } from './auth/RequireRole';

// Feature Pages
import { LoginPage } from './features/auth/LoginPage';
import { RegisterPage } from './features/auth/RegisterPage';
import { StaffRegisterPage } from './features/auth/StaffRegisterPage';
import { PendingApprovalPage } from './features/auth/PendingApprovalPage';
import { ProfilePage } from './features/auth/ProfilePage';
import { LookupPage } from './features/lookup/LookupPage';
import { ReportPage } from './features/report/ReportPage';
import { ReportSuccessPage } from './features/report/ReportSuccessPage';
import { TrackReportPage } from './features/report/TrackReportPage';
import { MyReportsPage } from './features/report/MyReportsPage';
import { LiteracyHubPage } from './features/hub/LiteracyHubPage';
import { GuideDetailPage } from './features/hub/GuideDetailPage';
import { EducatorStudioPage } from './features/hub/EducatorStudioPage';
import { SimulatorGamePage } from './features/simulator/SimulatorGamePage';
import { TriagePage } from './features/triage/TriagePage';
import { TrendAnalyticsPage } from './features/triage/TrendAnalyticsPage';
import { IndicatorManagementPage } from './features/triage/IndicatorManagementPage';
import { AdvisoryStudioPage } from './features/triage/AdvisoryStudioPage';
import { AdminDashboardPage } from './features/admin/AdminDashboardPage';

// Simple Landing Home & Error Handlers
import { HomePage } from './pages/HomePage';
import { UnauthorizedPage } from './pages/UnauthorizedPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const router = createBrowserRouter([
  // Public Portal Shell
  {
    path: '/',
    element: <PublicLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'lookup', element: <LookupPage /> },
      { path: 'report', element: <ReportPage /> },
      { path: 'report/success', element: <ReportSuccessPage /> },
      { path: 'report/track', element: <TrackReportPage /> },
      { path: 'track', element: <TrackReportPage /> },
      {
        path: 'my-reports',
        element: (
          <RequireRole>
            <MyReportsPage />
          </RequireRole>
        ),
      },
      { path: 'literacy', element: <LiteracyHubPage /> },
      { path: 'literacy/:slug', element: <GuideDetailPage /> },
      { path: 'guides', element: <LiteracyHubPage /> },
      { path: 'guides/:slug', element: <GuideDetailPage /> },
      { path: 'simulator', element: <SimulatorGamePage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'register/staff', element: <StaffRegisterPage /> },
      { path: 'pending-approval', element: <PendingApprovalPage /> },
      {
        path: 'profile',
        element: (
          <RequireRole>
            <ProfilePage />
          </RequireRole>
        ),
      },
      { path: 'unauthorized', element: <UnauthorizedPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },

  // Staff Portal Shell (Protected with Role Guards)
  {
    path: '/',
    element: <StaffLayout />,
    children: [
      {
        path: 'triage',
        element: (
          <RequireRole allowedRoles={['ANALYST', 'ADMIN']}>
            <TriagePage />
          </RequireRole>
        ),
      },
      {
        path: 'analyst/queue',
        element: (
          <RequireRole allowedRoles={['ANALYST', 'ADMIN']}>
            <TriagePage />
          </RequireRole>
        ),
      },
      {
        path: 'analyst/trends',
        element: (
          <RequireRole allowedRoles={['ANALYST', 'ADMIN']}>
            <TrendAnalyticsPage />
          </RequireRole>
        ),
      },
      {
        path: 'analyst/indicators',
        element: (
          <RequireRole allowedRoles={['ANALYST', 'ADMIN']}>
            <IndicatorManagementPage />
          </RequireRole>
        ),
      },
      {
        path: 'analyst/advisories',
        element: (
          <RequireRole allowedRoles={['ANALYST', 'ADMIN']}>
            <AdvisoryStudioPage />
          </RequireRole>
        ),
      },
      {
        path: 'studio',
        element: (
          <RequireRole allowedRoles={['EDUCATOR', 'ADMIN']}>
            <EducatorStudioPage />
          </RequireRole>
        ),
      },
      {
        path: 'studio/guides',
        element: (
          <RequireRole allowedRoles={['EDUCATOR', 'ADMIN']}>
            <EducatorStudioPage />
          </RequireRole>
        ),
      },
      {
        path: 'admin',
        element: (
          <RequireRole allowedRoles={['ADMIN']}>
            <AdminDashboardPage />
          </RequireRole>
        ),
      },
    ],
  },
]);
