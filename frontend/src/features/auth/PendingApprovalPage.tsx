import React from 'react';
import { Link } from 'react-router-dom';
import { Clock } from 'lucide-react';
import { Button } from '../../components/Button';
import { useAuth } from '../../auth/AuthProvider';

export const PendingApprovalPage: React.FC = () => {
  const { logout } = useAuth();

  return (
    <div className="max-w-md mx-auto px-4 py-20 text-center space-y-6">
      <div className="p-4 bg-amber-100 text-amber-800 rounded-full w-fit mx-auto">
        <Clock className="w-12 h-12" aria-hidden="true" />
      </div>

      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-slate-900">Application Pending Review</h1>
        <p className="text-sm text-slate-600 leading-relaxed">
          Your staff account application has been submitted and is awaiting administrative review. You will receive authorization once agency credentials are confirmed.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4">
        <Button variant="secondary" onClick={() => logout()}>
          Sign Out
        </Button>
        <Link to="/">
          <Button variant="outline">
            Return to Public Home
          </Button>
        </Link>
      </div>
    </div>
  );
};
