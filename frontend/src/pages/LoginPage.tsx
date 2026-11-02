import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { COPY } from '../lib/copy';
import { Input } from '../components/Input';
import { Button } from '../components/Button';
import { Alert } from '../components/Alert';
import { parseApiError } from '../api/errors';
import { Shield } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsLoading(true);

    try {
      const user = await login(email, password);
      if (['ANALYST', 'EDUCATOR', 'ADMIN'].includes(user.role)) {
        if (from !== '/') {
          navigate(from, { replace: true });
        } else if (user.role === 'ADMIN') {
          navigate('/admin', { replace: true });
        } else if (user.role === 'EDUCATOR') {
          navigate('/studio', { replace: true });
        } else {
          navigate('/triage', { replace: true });
        }
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      const parsed = parseApiError(err);
      if (parsed.code === 'account_not_approved') {
        setErrorMsg(COPY.auth.accountPending);
      } else if (parsed.code === 'authentication_failed' || parsed.status === 401) {
        setErrorMsg(COPY.auth.invalidCredentials);
      } else {
        setErrorMsg(parsed.message || COPY.errors.general);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-2">
        <div className="inline-flex p-3 bg-gov-blue text-white rounded-xl shadow-md mb-2">
          <Shield className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          {COPY.auth.loginTitle}
        </h1>
        <p className="text-sm text-slate-600">
          {COPY.auth.loginSubtitle}
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-xl space-y-6">
          {errorMsg && (
            <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
              {errorMsg}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              id="login-email"
              type="email"
              label={COPY.auth.emailLabel}
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />

            <Input
              id="login-password"
              type="password"
              label={COPY.auth.passwordLabel}
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />

            <Button
              type="submit"
              variant="primary"
              className="w-full mt-2"
              isLoading={isLoading}
            >
              {COPY.auth.submitLogin}
            </Button>
          </form>

          <div className="border-t border-slate-100 pt-4 text-center text-xs text-slate-600 space-y-2">
            <div>
              Don&apos;t have an account?{' '}
              <Link to="/register" className="font-semibold text-gov-blue hover:underline">
                {COPY.nav.register}
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
