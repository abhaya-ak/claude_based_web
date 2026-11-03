import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { COPY } from '../../lib/copy';
import { UserPlus } from 'lucide-react';
import { Input } from '../../components/Input';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import { authApi } from '../../api/auth';
import { parseApiError } from '../../api/errors';

export const RegisterPage: React.FC = () => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (password !== confirmPassword) {
      setErrorMsg('Passwords do not match.');
      return;
    }

    if (password.length < 10) {
      setErrorMsg('Password must be at least 10 characters long.');
      return;
    }

    setIsLoading(true);

    try {
      await authApi.register({
        email,
        password,
        full_name: fullName,
      });

      setSuccessMsg('Account created successfully! Redirecting to sign in...');
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      const parsed = parseApiError(err);
      setErrorMsg(parsed.message || 'Registration failed. Please verify your details.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-2">
        <div className="inline-flex p-3 bg-slate-900 text-white rounded-xl shadow-md mb-2">
          <UserPlus className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          {COPY.auth.registerTitle}
        </h1>
        <p className="text-sm text-slate-600">
          {COPY.auth.registerSubtitle}
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-xl space-y-6">
          {errorMsg && (
            <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
              {errorMsg}
            </Alert>
          )}

          {successMsg && (
            <Alert variant="success">
              {successMsg}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              id="reg-fullname"
              label={COPY.auth.fullNameLabel}
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />

            <Input
              id="reg-email"
              type="email"
              label={COPY.auth.emailLabel}
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />

            <Input
              id="reg-password"
              type="password"
              label={COPY.auth.passwordLabel}
              required
              helperText="Minimum 10 characters"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />

            <Input
              id="reg-confirm-password"
              type="password"
              label={COPY.auth.confirmPasswordLabel}
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />

            <Button
              type="submit"
              variant="primary"
              className="w-full mt-2"
              isLoading={isLoading}
            >
              {COPY.auth.submitRegister}
            </Button>
          </form>

          <div className="border-t border-slate-100 pt-4 text-center text-xs text-slate-600">
            Already have an account?{' '}
            <Link to="/login" className="font-semibold text-slate-900 hover:underline">
              {COPY.nav.login}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
