import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/Button';
import { FileQuestion } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="max-w-md mx-auto px-4 py-20 text-center space-y-6">
      <div className="p-4 bg-slate-100 text-slate-500 rounded-full w-fit mx-auto">
        <FileQuestion className="w-12 h-12" aria-hidden="true" />
      </div>

      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-slate-900">404 — Page Not Found</h1>
        <p className="text-sm text-slate-600 leading-relaxed">
          The requested page could not be located on the ScamShield portal.
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
