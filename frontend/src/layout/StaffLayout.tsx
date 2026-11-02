import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { AccessibilityBar } from './AccessibilityBar';
import { useAuth } from '../auth/AuthProvider';
import { COPY } from '../lib/copy';
import {
  ShieldAlert,
  ClipboardList,
  BookOpen,
  Sliders,
  LogOut,
  ArrowLeft,
  UserCheck,
} from 'lucide-react';

export const StaffLayout: React.FC = () => {
  const { user, logout, role } = useAuth();
  const location = useLocation();

  const getNavItems = () => {
    const items = [];

    if (role === 'ANALYST' || role === 'ADMIN') {
      items.push({
        to: '/triage',
        label: COPY.nav.triage,
        icon: <ClipboardList className="w-4 h-4" />,
      });
    }

    if (role === 'EDUCATOR' || role === 'ADMIN') {
      items.push({
        to: '/studio',
        label: COPY.nav.studio,
        icon: <BookOpen className="w-4 h-4" />,
      });
    }

    if (role === 'ADMIN') {
      items.push({
        to: '/admin',
        label: COPY.nav.admin,
        icon: <Sliders className="w-4 h-4" />,
      });
    }

    return items;
  };

  const navItems = getNavItems();

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 text-slate-900 font-sans">
      <AccessibilityBar />

      {/* Staff Top Navigation */}
      <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Staff Brand & Public Switch */}
            <div className="flex items-center gap-4">
              <Link
                to="/"
                className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors"
                title="Return to Public Portal"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Public Site</span>
              </Link>
              <div className="h-4 w-px bg-slate-700" aria-hidden="true" />
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-amber-400" aria-hidden="true" />
                <span className="font-bold text-base tracking-tight text-white">
                  ScamShield Staff
                </span>
                <span className="ml-2 px-2 py-0.5 text-[10px] uppercase font-bold tracking-wider rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  {role}
                </span>
              </div>
            </div>

            {/* Role Navigation */}
            <nav className="hidden md:flex items-center space-x-1" aria-label="Staff Navigation">
              {navItems.map((item) => {
                const isActive = location.pathname.startsWith(item.to);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    aria-current={isActive ? 'page' : undefined}
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-white ${
                      isActive
                        ? 'bg-slate-800 text-amber-400 border border-slate-700'
                        : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                    }`}
                  >
                    {item.icon}
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>

            {/* Profile & Logout */}
            <div className="flex items-center gap-3">
              <div className="hidden sm:flex flex-col text-right">
                <span className="text-xs font-semibold text-white leading-tight">
                  {user?.full_name}
                </span>
                <span className="text-[10px] text-slate-400 leading-tight">
                  {user?.organization || user?.email}
                </span>
              </div>
              <div className="p-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                <UserCheck className="w-4 h-4" />
              </div>
              <button
                type="button"
                onClick={() => logout()}
                className="inline-flex items-center gap-1 text-xs font-semibold text-slate-400 hover:text-red-400 p-1.5 rounded transition-colors"
                title={COPY.nav.logout}
                aria-label={COPY.nav.logout}
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Staff Content */}
      <main id="main-content" tabIndex={-1} className="flex-1 focus:outline-none py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <Outlet />
        </div>
      </main>

      {/* Staff Minimal Footer */}
      <footer className="bg-white border-t border-slate-200 text-slate-500 text-xs py-3 text-center">
        <span>ScamShield Agency Staff Environment — Authorized Access Only</span>
      </footer>
    </div>
  );
};
