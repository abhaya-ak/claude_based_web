import React from 'react';
import { Link } from 'react-router-dom';
import { COPY } from '../lib/copy';
import { UserPlus } from 'lucide-react';
import { Button } from '../components/Button';

export const RegisterPage: React.FC = () => {
  return (
    <div className="min-h-[80vh] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-2">
        <div className="inline-flex p-3 bg-gov-blue text-white rounded-xl shadow-md mb-2">
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
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-xl space-y-6 text-center">
          <p className="text-sm text-slate-600">
            Citizen registration and staff onboarding forms will initialize in Slice F2.
          </p>

          <div className="space-y-3">
            <Link to="/login">
              <Button variant="secondary" className="w-full">
                Return to Sign In
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
