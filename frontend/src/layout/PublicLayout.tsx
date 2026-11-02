import React, { useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { AccessibilityBar } from './AccessibilityBar';
import { useAuth } from '../auth/AuthProvider';
import { COPY } from '../lib/copy';
import { Shield, Menu, X, ShieldAlert, LogOut, User as UserIcon } from 'lucide-react';

export const PublicLayout: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user, isAuthenticated, logout, role } = useAuth();
  const location = useLocation();

  const navLinks = [
    { to: '/', label: COPY.nav.home },
    { to: '/lookup', label: COPY.nav.lookup },
    { to: '/report', label: COPY.nav.report },
    { to: '/literacy', label: COPY.nav.literacy },
    { to: '/simulator', label: COPY.nav.simulator },
  ];

  const isStaff = role && ['ANALYST', 'EDUCATOR', 'ADMIN'].includes(role);

  const getStaffPortalPath = () => {
    if (role === 'ADMIN') return '/admin';
    if (role === 'EDUCATOR') return '/studio';
    return '/triage';
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 font-sans">
      {/* Top Accessibility Bar */}
      <AccessibilityBar />

      {/* Main Header / Navigation */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo and Brand */}
            <div className="flex items-center gap-3">
              <Link
                to="/"
                className="flex items-center gap-2.5 text-gov-blue hover:text-gov-navy transition-colors focus-visible:outline focus-visible:outline-2"
                aria-label="ScamShield Home"
              >
                <div className="bg-gov-blue text-white p-2 rounded-lg shadow-sm">
                  <Shield className="w-6 h-6" aria-hidden="true" />
                </div>
                <div className="flex flex-col">
                  <span className="text-xl font-bold tracking-tight text-slate-900">
                    {COPY.brand.name}
                  </span>
                  <span className="text-[11px] font-medium text-slate-500 hidden sm:inline">
                    {COPY.brand.subtitle}
                  </span>
                </div>
              </Link>
            </div>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center space-x-1" aria-label="Primary Navigation">
              {navLinks.map((link) => {
                const isActive = location.pathname === link.to;
                return (
                  <Link
                    key={link.to}
                    to={link.to}
                    aria-current={isActive ? 'page' : undefined}
                    className={`px-3 py-2 rounded-md text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 ${
                      isActive
                        ? 'text-gov-blue bg-blue-50/70 border-b-2 border-gov-blue'
                        : 'text-slate-700 hover:text-gov-blue hover:bg-slate-100'
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>

            {/* Auth Actions / User Menu */}
            <div className="hidden md:flex items-center gap-3">
              {isAuthenticated && user ? (
                <div className="flex items-center gap-3">
                  {isStaff && (
                    <Link
                      to={getStaffPortalPath()}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-amber-100 text-amber-900 hover:bg-amber-200 transition-colors"
                    >
                      <ShieldAlert className="w-3.5 h-3.5" />
                      <span>{COPY.nav.staffPortal}</span>
                    </Link>
                  )}
                  <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 bg-slate-100 px-2.5 py-1 rounded-full">
                    <UserIcon className="w-3.5 h-3.5" />
                    <span className="max-w-[120px] truncate">{user.full_name}</span>
                    <span className="text-[10px] uppercase font-bold text-slate-500">
                      ({user.role})
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => logout()}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-gov-red p-1.5 rounded transition-colors"
                    aria-label={COPY.nav.logout}
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link
                    to="/login"
                    className="px-3.5 py-2 text-sm font-semibold text-slate-700 hover:text-gov-blue hover:bg-slate-100 rounded-md transition-colors"
                  >
                    {COPY.nav.login}
                  </Link>
                  <Link
                    to="/register"
                    className="px-4 py-2 text-sm font-semibold text-white bg-gov-blue hover:bg-gov-navy rounded-md shadow-sm transition-colors"
                  >
                    {COPY.nav.register}
                  </Link>
                </div>
              )}
            </div>

            {/* Mobile Menu Button */}
            <div className="flex md:hidden">
              <button
                type="button"
                onClick={() => setMobileMenuOpen((prev) => !prev)}
                className="p-2 rounded-md text-slate-700 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2"
                aria-expanded={mobileMenuOpen}
                aria-label="Toggle mobile menu"
              >
                {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-slate-200 bg-white px-4 pt-3 pb-4 space-y-2">
            <nav className="flex flex-col space-y-1">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-2 rounded-md text-base font-medium text-slate-800 hover:bg-slate-100"
                >
                  {link.label}
                </Link>
              ))}
            </nav>
            <div className="pt-3 border-t border-slate-200 flex flex-col gap-2">
              {isAuthenticated && user ? (
                <>
                  <div className="text-xs text-slate-600 px-3">
                    Signed in as <strong className="text-slate-900">{user.full_name}</strong> ({user.role})
                  </div>
                  {isStaff && (
                    <Link
                      to={getStaffPortalPath()}
                      onClick={() => setMobileMenuOpen(false)}
                      className="w-full text-center py-2 text-sm font-bold bg-amber-100 text-amber-900 rounded"
                    >
                      {COPY.nav.staffPortal}
                    </Link>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      logout();
                      setMobileMenuOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 text-sm font-medium text-gov-red hover:bg-red-50 rounded"
                  >
                    {COPY.nav.logout}
                  </button>
                </>
              ) : (
                <div className="flex flex-col gap-2">
                  <Link
                    to="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full text-center py-2 text-sm font-semibold text-slate-700 border border-slate-300 rounded"
                  >
                    {COPY.nav.login}
                  </Link>
                  <Link
                    to="/register"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full text-center py-2 text-sm font-semibold text-white bg-gov-blue rounded"
                  >
                    {COPY.nav.register}
                  </Link>
                </div>
              )}
            </div>
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main id="main-content" tabIndex={-1} className="flex-1 focus:outline-none">
        <Outlet />
      </main>

      {/* Public Footer */}
      <footer className="bg-slate-900 text-slate-400 text-xs border-t border-slate-800 mt-auto">
        <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8 space-y-4">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-gov-yellow" aria-hidden="true" />
              <span className="font-bold text-white text-sm">{COPY.brand.name}</span>
              <span className="text-slate-500">|</span>
              <span>{COPY.brand.govNotice}</span>
            </div>
            <div className="text-center md:text-right text-slate-500">
              {COPY.brand.copyright}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};
