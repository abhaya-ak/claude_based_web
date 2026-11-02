import { createBrowserRouter } from 'react-router-dom';
import { PublicLayout } from './layout/PublicLayout';
import { StaffLayout } from './layout/StaffLayout';
import { RequireRole } from './auth/RequireRole';

// Public Pages
import { HomePage } from './pages/HomePage';
import { LookupPage } from './pages/LookupPage';
import { ReportPage } from './pages/ReportPage';
import { LiteracyPage } from './pages/LiteracyPage';
import { SimulatorPage } from './pages/SimulatorPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { UnauthorizedPage } from './pages/UnauthorizedPage';
import { NotFoundPage } from './pages/NotFoundPage';

// Staff Pages
import { TriagePage } from './pages/staff/TriagePage';
import { StudioPage } from './pages/staff/StudioPage';
import { AdminPage } from './pages/staff/AdminPage';

export const router = createBrowserRouter([
  // Public Portal Shell
  {
    path: '/',
    element: <PublicLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'lookup', element: <LookupPage /> },
      { path: 'report', element: <ReportPage /> },
      { path: 'literacy', element: <LiteracyPage /> },
      { path: 'simulator', element: <SimulatorPage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
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
        path: 'studio',
        element: (
          <RequireRole allowedRoles={['EDUCATOR', 'ADMIN']}>
            <StudioPage />
          </RequireRole>
        ),
      },
      {
        path: 'admin',
        element: (
          <RequireRole allowedRoles={['ADMIN']}>
            <AdminPage />
          </RequireRole>
        ),
      },
    ],
  },
]);
