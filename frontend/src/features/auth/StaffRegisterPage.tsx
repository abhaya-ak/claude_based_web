import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { COPY } from '../../lib/copy';
import { ShieldAlert } from 'lucide-react';
import { Input } from '../../components/Input';
import { Select } from '../../components/Select';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import { authApi } from '../../api/auth';
import { parseApiError } from '../../api/errors';

export const StaffRegisterPage: React.FC = () => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'ANALYST' | 'EDUCATOR'>('ANALYST');
  const [organization, setOrganization] = useState('');
  const [credentialNote, setCredentialNote] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const navigate = useNavigate();

  const roleOptions = [
    { value: 'ANALYST', label: 'Fraud Analyst / Law Enforcement Investigator' },
    { value: 'EDUCATOR', label: 'Security Awareness Educator / Content Author' },
  ];

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

    if (!credentialNote.trim()) {
      setErrorMsg('Please provide a credential or verification note.');
      return;
    }

    setIsLoading(true);

    try {
      await authApi.registerStaff({
        email,
        password,
        full_name: fullName,
        role,
        organization,
        credential_note: credentialNote,
      });

      navigate('/pending-approval');
    } catch (err) {
      const parsed = parseApiError(err);
      setErrorMsg(parsed.message || 'Staff application failed. Please verify your details.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-2">
        <div className="inline-flex p-3 bg-amber-500/10 border border-amber-500/30 text-amber-700 rounded-xl shadow-sm mb-2">
          <ShieldAlert className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Agency Staff Application
        </h1>
        <p className="text-sm text-slate-600">
          Verified access for certified law enforcement officers and educators.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-lg px-4">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-xl space-y-6">
          {errorMsg && (
            <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
              {errorMsg}
            </Alert>
          )}

          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900">
            <strong>Mandatory Verification Notice:</strong> All staff applications are subjected to strict administrative approval before portal access is granted.
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Select
              id="staff-role"
              label="Requested Agency Role"
              value={role}
              onChange={(e) => setRole(e.target.value as 'ANALYST' | 'EDUCATOR')}
              options={roleOptions}
            />

            <Input
              id="staff-fullname"
              label={COPY.auth.fullNameLabel}
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />

            <Input
              id="staff-email"
              type="email"
              label="Official Agency Email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />

            <Input
              id="staff-org"
              label="Agency / Institution Name"
              placeholder="e.g. Royal Malaysia Police (CCID), CyberSecurity Malaysia, or University"
              required
              value={organization}
              onChange={(e) => setOrganization(e.target.value)}
            />

            <div className="space-y-1.5 text-left">
              <label htmlFor="staff-cred" className="block text-sm font-semibold text-slate-800">
                Official Credential / Badge Details <span className="text-red-600">*</span>
              </label>
              <textarea
                id="staff-cred"
                required
                rows={3}
                className="w-full rounded-md border border-slate-300 p-3 text-sm focus-visible:outline focus-visible:outline-slate-900"
                placeholder="State your badge/officer ID, agency branch, or institutional accreditation..."
                value={credentialNote}
                onChange={(e) => setCredentialNote(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                id="staff-password"
                type="password"
                label={COPY.auth.passwordLabel}
                required
                helperText="Min 10 characters"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />

              <Input
                id="staff-confirm-password"
                type="password"
                label={COPY.auth.confirmPasswordLabel}
                required
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full mt-2"
              isLoading={isLoading}
            >
              Submit Staff Application
            </Button>
          </form>

          <div className="border-t border-slate-100 pt-4 text-center text-xs text-slate-600">
            Citizen user instead?{' '}
            <Link to="/register" className="font-semibold text-slate-900 hover:underline">
              {COPY.nav.register}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
