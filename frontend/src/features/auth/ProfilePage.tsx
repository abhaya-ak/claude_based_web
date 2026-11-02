import React, { useState } from 'react';
import { useAuth } from '../../auth/AuthProvider';
import { Input } from '../../components/Input';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import { authApi } from '../../api/auth';
import { parseApiError } from '../../api/errors';
import { User, KeyRound, ShieldCheck } from 'lucide-react';
import { formatDate } from '../../lib/format';

export const ProfilePage: React.FC = () => {
  const { user, logout } = useAuth();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);

    if (newPassword !== confirmPassword) {
      setErrorMsg('New passwords do not match.');
      return;
    }

    if (newPassword.length < 10) {
      setErrorMsg('New password must be at least 10 characters long.');
      return;
    }

    setIsLoading(true);

    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });

      setSuccessMsg('Password updated successfully! For security, please sign in again.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');

      setTimeout(() => logout(), 2500);
    } catch (err) {
      const parsed = parseApiError(err);
      setErrorMsg(parsed.message || 'Failed to update password.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!user) return null;

  return (
    <div className="max-w-3xl mx-auto px-4 py-12 space-y-8">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <User className="w-6 h-6 text-slate-900" />
          <span>User Account & Security Profile</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Review your account credentials and update security preferences.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Profile Summary Card */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Identity Details</span>
          </h2>

          <div className="space-y-3 text-sm">
            <div>
              <span className="text-xs text-slate-400 block">Full Name</span>
              <strong className="text-slate-900">{user.full_name}</strong>
            </div>

            <div>
              <span className="text-xs text-slate-400 block">Email Address</span>
              <span className="text-slate-800">{user.email}</span>
            </div>

            <div>
              <span className="text-xs text-slate-400 block">Assigned Role</span>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-800">
                {user.role}
              </span>
            </div>

            <div>
              <span className="text-xs text-slate-400 block">Approval Status</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${
                user.approval_status === 'APPROVED'
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-amber-100 text-amber-800'
              }`}>
                {user.approval_status}
              </span>
            </div>

            {user.organization && (
              <div>
                <span className="text-xs text-slate-400 block">Organization</span>
                <span className="text-slate-700">{user.organization}</span>
              </div>
            )}

            <div>
              <span className="text-xs text-slate-400 block">Member Since</span>
              <span className="text-slate-600">{formatDate(user.created_at)}</span>
            </div>
          </div>
        </div>

        {/* Password Change Card */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
            <KeyRound className="w-4 h-4 text-slate-900" />
            <span>Update Password</span>
          </h2>

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

          <form onSubmit={handlePasswordChange} className="space-y-3">
            <Input
              id="curr-pass"
              type="password"
              label="Current Password"
              required
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />

            <Input
              id="new-pass"
              type="password"
              label="New Password"
              required
              helperText="Min 10 characters"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />

            <Input
              id="confirm-new-pass"
              type="password"
              label="Confirm New Password"
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
              Update Password
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};
