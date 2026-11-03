import React from 'react';
import { Link } from 'react-router-dom';
import { COPY } from '../lib/copy';
import { ShieldX } from 'lucide-react';
import { Button } from '../components/Button';

export const UnauthorizedPage: React.FC = () => {
  return (
    <div className="max-w-md mx-auto px-4 py-20 text-center space-y-6">
      <div className="p-4 bg-red-100 text-gov-red rounded-full w-fit mx-auto">
        <ShieldX className="w-12 h-12" aria-hidden="true" />
      </div>

      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-slate-900">Access Restricted</h1>
        <p className="text-sm text-slate-600 leading-relaxed">
          {COPY.errors.forbidden}
        </p>
      </div>

      <div className="pt-2">
        <Link to="/">
          <Button variant="primary">Return to Home</Button>
        </Link>
      </div>
    </div>
  );
};
