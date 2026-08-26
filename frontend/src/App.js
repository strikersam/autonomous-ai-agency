import React, { Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import LoginPage from './pages/LoginPage';
import AuthCallback from './pages/AuthCallback';
import SetupWizardPage from './pages/SetupWizardPage';

const V5App = React.lazy(() => import('./v5/V5App'));

function LoadingScreen({ message }) {
  return (
    <div className="app-shell min-h-[100dvh] flex items-center justify-center px-4">
      <div className="app-panel-elevated flex flex-col items-center gap-3 px-8 py-8 text-center">
        <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: "var(--accent)" }} />
        <p className="text-[var(--text-muted)] text-xs font-mono tracking-[0.18em] uppercase">{message}</p>
      </div>
    </div>
  );
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <LoadingScreen message="Authenticating" />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) return <LoadingScreen message="Initializing" />;
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* Pre-auth setup wizard — configure backend URL before logging in */}
      <Route path="/bootstrap" element={<SetupWizardPage />} />

      {/* The Agency — the only authenticated UI. The legacy v4 dashboard that
          used to live at /legacy/* was removed after the v5 IA consolidation;
          old /v5/<screen> deep links are aliased inside V5App. */}
      <Route
        path="/v5/*"
        element={
          <ProtectedRoute>
            <Suspense fallback={<LoadingScreen message="Loading the Agency" />}>
              <V5App />
            </Suspense>
          </ProtectedRoute>
        }
      />

      {/* Default: redirect authenticated users into the Agency */}
      <Route
        path="/*"
        element={user ? <Navigate to="/v5" replace /> : <Navigate to="/login" replace />}
      />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
