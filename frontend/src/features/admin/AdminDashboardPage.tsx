import React, { useState, useEffect } from 'react';
import { adminApi } from '../../api/admin';
import type { User, AuditLogItem } from '../../api/schema';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import { Users, FileText, Check, X, Shield } from 'lucide-react';
import { formatDate } from '../../lib/format';

export const AdminDashboardPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'users' | 'audit'>('users');
  const [users, setUsers] = useState<User[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    try {
      if (activeTab === 'users') {
        const res = await adminApi.getUsers();
        setUsers(res.results || []);
      } else {
        const res = await adminApi.getAuditLogs();
        setAuditLogs(res.results || []);
      }
    } catch {
      // Offline fallback
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const handleApprove = async (id: string) => {
    try {
      await adminApi.approveUser(id);
      setActionNotice('Staff account approved.');
      loadData();
    } catch {
      setActionNotice('Failed to approve user.');
    }
  };

  const handleReject = async (id: string) => {
    try {
      await adminApi.rejectUser(id, 'Qualifications could not be independently verified.');
      setActionNotice('Staff account rejected.');
      loadData();
    } catch {
      setActionNotice('Failed to reject user.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Shield className="w-6 h-6 text-slate-900" />
            <span>Administrative Console</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Review staff applications, monitor audit trail events, and manage system operations.
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            size="sm"
            variant={activeTab === 'users' ? 'primary' : 'secondary'}
            onClick={() => setActiveTab('users')}
            leftIcon={<Users className="w-4 h-4" />}
          >
            Staff Applications
          </Button>
          <Button
            size="sm"
            variant={activeTab === 'audit' ? 'primary' : 'secondary'}
            onClick={() => setActiveTab('audit')}
            leftIcon={<FileText className="w-4 h-4" />}
          >
            Audit Logs
          </Button>
        </div>
      </div>

      {actionNotice && (
        <Alert variant="info" onDismiss={() => setActionNotice(null)}>
          {actionNotice}
        </Alert>
      )}

      {/* Main Content Area */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-sm text-slate-500">Loading administrative records...</div>
        ) : activeTab === 'users' ? (
          /* Staff Approvals Table */
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-semibold">
                <tr>
                  <th className="p-3.5">Name</th>
                  <th className="p-3.5">Email</th>
                  <th className="p-3.5">Requested Role</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5">Organization</th>
                  <th className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-slate-400">
                      No staff accounts found.
                    </td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50/60">
                      <td className="p-3.5 font-bold text-slate-900">{u.full_name}</td>
                      <td className="p-3.5 text-slate-600">{u.email}</td>
                      <td className="p-3.5 font-semibold text-slate-800">{u.role}</td>
                      <td className="p-3.5">
                        <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                          u.approval_status === 'APPROVED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : u.approval_status === 'REJECTED'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}>
                          {u.approval_status}
                        </span>
                      </td>
                      <td className="p-3.5 text-slate-500">{u.organization || '—'}</td>
                      <td className="p-3.5 text-right space-x-2">
                        {u.approval_status === 'PENDING' ? (
                          <>
                            <button
                              type="button"
                              onClick={() => handleApprove(u.id)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-600 text-white font-semibold hover:bg-emerald-700"
                            >
                              <Check className="w-3.5 h-3.5" />
                              Approve
                            </button>
                            <button
                              type="button"
                              onClick={() => handleReject(u.id)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-red-600 text-white font-semibold hover:bg-red-700"
                            >
                              <X className="w-3.5 h-3.5" />
                              Reject
                            </button>
                          </>
                        ) : (
                          <span className="text-slate-400">Processed</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : (
          /* Audit Logs Table */
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-semibold">
                <tr>
                  <th className="p-3.5">Timestamp</th>
                  <th className="p-3.5">Event Type</th>
                  <th className="p-3.5">Severity</th>
                  <th className="p-3.5">Actor</th>
                  <th className="p-3.5">Target</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-slate-400">
                      No audit events recorded in current period.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/60 font-mono">
                      <td className="p-3.5 text-slate-600 font-sans">{formatDate(log.created_at)}</td>
                      <td className="p-3.5 font-bold text-slate-900">{log.event_type}</td>
                      <td className="p-3.5">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          log.severity === 'CRITICAL' || log.severity === 'HIGH'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-slate-100 text-slate-700'
                        }`}>
                          {log.severity}
                        </span>
                      </td>
                      <td className="p-3.5 text-slate-600">{log.actor_email || log.actor_id || 'System'}</td>
                      <td className="p-3.5 text-slate-500">{log.target_type}: {log.target_id}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
