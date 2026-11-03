import React, { useState, useEffect } from 'react';
import { adminApi, type HeuristicRule, type ScannerConfig, type TelemetryMetrics } from '../../api/admin';
import type { User, AuditLogItem, UserRole } from '../../api/schema';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import { Modal } from '../../components/Modal';
import {
  Shield,
  Users,
  FileText,
  Activity,
  Sliders,
  Check,
  X,
  Download,
  AlertTriangle,
  Server,
  Database,
  Radio,
  Search,
} from 'lucide-react';
import { formatDate } from '../../lib/format';

export const AdminDashboardPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'users' | 'audit' | 'telemetry' | 'rules'>('users');
  const [isLoading, setIsLoading] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  // Tab 1: Users State
  const [users, setUsers] = useState<User[]>([]);
  const [userStatusFilter, setUserStatusFilter] = useState<'ALL' | 'PENDING' | 'APPROVED' | 'REJECTED'>('ALL');
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const [rejectingUser, setRejectingUser] = useState<User | null>(null);
  const [rejectionReason, setRejectionReason] = useState('Official credentials could not be verified with issuing authority.');
  const [roleChangeUser, setRoleChangeUser] = useState<User | null>(null);
  const [selectedNewRole, setSelectedNewRole] = useState<UserRole>('ANALYST');

  // Tab 2: Audit Logs State
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [auditSeverityFilter, setAuditSeverityFilter] = useState('ALL');
  const [inspectAuditLog, setInspectAuditLog] = useState<AuditLogItem | null>(null);

  // Tab 3: Telemetry State
  const [telemetry, setTelemetry] = useState<TelemetryMetrics | null>(null);

  // Tab 4: Scanner Rules & Config State
  const [rules, setRules] = useState<HeuristicRule[]>([]);
  const [scannerConfig, setScannerConfig] = useState<ScannerConfig | null>(null);

  const loadTabData = async () => {
    setIsLoading(true);
    setErrorNotice(null);
    try {
      if (activeTab === 'users') {
        const res = await adminApi.getUsers();
        setUsers(res.results || []);
      } else if (activeTab === 'audit') {
        const res = await adminApi.getAuditLogs({
          severity: auditSeverityFilter === 'ALL' ? undefined : auditSeverityFilter,
        });
        setAuditLogs(res.results || []);
      } else if (activeTab === 'telemetry') {
        const res = await adminApi.getTelemetryMetrics();
        setTelemetry(res);
      } else if (activeTab === 'rules') {
        const [rulesRes, configRes] = await Promise.all([
          adminApi.getRules(),
          adminApi.getScannerConfig(),
        ]);
        setRules(rulesRes.results || []);
        setScannerConfig(configRes);
      }
    } catch {
      setErrorNotice('Failed to load records from the administrative service.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTabData();
  }, [activeTab, auditSeverityFilter]);

  // User Actions
  const handleApprove = async (id: string) => {
    try {
      await adminApi.approveUser(id);
      setActionNotice('Staff account approved.');
      loadTabData();
    } catch {
      setErrorNotice('Failed to approve user.');
    }
  };

  const handleConfirmReject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rejectingUser) return;
    try {
      await adminApi.rejectUser(rejectingUser.id, rejectionReason.trim());
      setActionNotice(`Staff account for ${rejectingUser.full_name} rejected.`);
      setRejectingUser(null);
      loadTabData();
    } catch {
      setErrorNotice('Failed to reject user.');
    }
  };

  const handleConfirmRoleChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roleChangeUser) return;
    try {
      await adminApi.changeRole(roleChangeUser.id, selectedNewRole);
      setActionNotice(`Role updated to ${selectedNewRole} for ${roleChangeUser.full_name}.`);
      setRoleChangeUser(null);
      loadTabData();
    } catch {
      setErrorNotice('Failed to update role.');
    }
  };

  const filteredUsers = users.filter((u) => {
    const matchesStatus = userStatusFilter === 'ALL' || u.approval_status === userStatusFilter;
    const matchesSearch =
      u.full_name.toLowerCase().includes(userSearchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(userSearchQuery.toLowerCase()) ||
      (u.organization && u.organization.toLowerCase().includes(userSearchQuery.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <Shield className="w-7 h-7 text-slate-900" />
            <span>Administrative Command Console</span>
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Access management, tamper-evident audit ledger, CloudWatch telemetry, and heuristic scanner rules.
          </p>
        </div>

        {/* Tab Navigation Controls */}
        <div className="flex flex-wrap gap-1.5 bg-slate-200/80 p-1 rounded-xl text-xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab('users')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'users'
                ? 'bg-white text-slate-900 shadow-sm font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Staff Applications</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('audit')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'audit'
                ? 'bg-white text-slate-900 shadow-sm font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Audit Logs</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('telemetry')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'telemetry'
                ? 'bg-white text-slate-900 shadow-sm font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Telemetry & Metrics</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('rules')}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'rules'
                ? 'bg-white text-slate-900 shadow-sm font-bold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Scanner Rules</span>
          </button>
        </div>
      </div>

      {actionNotice && (
        <Alert variant="success" onDismiss={() => setActionNotice(null)}>
          {actionNotice}
        </Alert>
      )}

      {errorNotice && (
        <Alert variant="error" onDismiss={() => setErrorNotice(null)}>
          {errorNotice}
        </Alert>
      )}

      {/* TAB 1: USERS & APPROVALS */}
      {activeTab === 'users' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-sm text-xs">
            <div className="flex items-center gap-2 flex-1 max-w-sm">
              <Search className="w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search staff by name, email, agency..."
                value={userSearchQuery}
                onChange={(e) => setUserSearchQuery(e.target.value)}
                className="w-full text-xs outline-none bg-transparent placeholder:text-slate-400"
              />
            </div>

            <div className="flex items-center gap-1.5">
              {(['ALL', 'PENDING', 'APPROVED', 'REJECTED'] as const).map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setUserStatusFilter(st)}
                  className={`px-3 py-1 rounded-md text-xs font-semibold transition-colors ${
                    userStatusFilter === st
                      ? 'bg-slate-900 text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-bold tracking-wider">
                  <tr>
                    <th className="p-3.5">Name</th>
                    <th className="p-3.5">Email</th>
                    <th className="p-3.5">Assigned Role</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5">Organization</th>
                    <th className="p-3.5">Applied Date</th>
                    <th className="p-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {isLoading ? (
                    <tr>
                      <td colSpan={7} className="p-8 text-center text-slate-400">
                        Loading staff records...
                      </td>
                    </tr>
                  ) : filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="p-8 text-center text-slate-400">
                        No staff accounts matching criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map((u) => (
                      <tr key={u.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="p-3.5 font-bold text-slate-900">{u.full_name}</td>
                        <td className="p-3.5 text-slate-600">{u.email}</td>
                        <td className="p-3.5">
                          <span className="px-2 py-0.5 rounded font-mono font-bold bg-slate-100 text-slate-800 text-[11px]">
                            {u.role}
                          </span>
                        </td>
                        <td className="p-3.5">
                          <span
                            className={`px-2 py-0.5 rounded font-bold text-[10px] uppercase ${
                              u.approval_status === 'APPROVED'
                                ? 'bg-emerald-100 text-emerald-800'
                                : u.approval_status === 'REJECTED'
                                ? 'bg-red-100 text-red-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}
                          >
                            {u.approval_status}
                          </span>
                        </td>
                        <td className="p-3.5 text-slate-600">{u.organization || '—'}</td>
                        <td className="p-3.5 text-slate-400 whitespace-nowrap">{formatDate(u.created_at)}</td>
                        <td className="p-3.5 text-right space-x-1.5 whitespace-nowrap">
                          {u.approval_status === 'PENDING' ? (
                            <>
                              <button
                                type="button"
                                onClick={() => handleApprove(u.id)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-600 text-white font-semibold hover:bg-emerald-700 transition-colors"
                              >
                                <Check className="w-3.5 h-3.5" />
                                <span>Approve</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => setRejectingUser(u)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-red-600 text-white font-semibold hover:bg-red-700 transition-colors"
                              >
                                <X className="w-3.5 h-3.5" />
                                <span>Reject</span>
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              onClick={() => {
                                setRoleChangeUser(u);
                                setSelectedNewRole(u.role);
                              }}
                              className="text-xs text-slate-600 hover:text-slate-900 font-semibold px-2 py-1 rounded hover:bg-slate-100 transition-colors"
                            >
                              Edit Role
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: AUDIT LOGS */}
      {activeTab === 'audit' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-sm text-xs">
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-600">Severity:</span>
              {(['ALL', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] as const).map((sev) => (
                <button
                  key={sev}
                  type="button"
                  onClick={() => setAuditSeverityFilter(sev)}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-colors ${
                    auditSeverityFilter === sev
                      ? 'bg-slate-900 text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  {sev}
                </button>
              ))}
            </div>

            <a
              href="/api/v1/admin-portal/audit-logs/export-csv/"
              download="audit-logs.csv"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 font-semibold transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </a>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-bold font-sans">
                  <tr>
                    <th className="p-3.5">Timestamp</th>
                    <th className="p-3.5">Event Type</th>
                    <th className="p-3.5">Severity</th>
                    <th className="p-3.5">Actor</th>
                    <th className="p-3.5">Target</th>
                    <th className="p-3.5 text-right font-sans">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {isLoading ? (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-slate-400 font-sans">
                        Querying immutable audit ledger...
                      </td>
                    </tr>
                  ) : auditLogs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-slate-400 font-sans">
                        No audit events recorded for selected severity.
                      </td>
                    </tr>
                  ) : (
                    auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="p-3.5 text-slate-600 font-sans whitespace-nowrap">{formatDate(log.created_at)}</td>
                        <td className="p-3.5 font-bold text-slate-900">{log.event_type}</td>
                        <td className="p-3.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              log.severity === 'CRITICAL' || log.severity === 'ERROR'
                                ? 'bg-red-100 text-red-800'
                                : log.severity === 'WARNING'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            {log.severity}
                          </span>
                        </td>
                        <td className="p-3.5 text-slate-600">{log.actor_email || log.actor_id || 'System'}</td>
                        <td className="p-3.5 text-slate-500">
                          {log.target_type}: {log.target_id.slice(0, 8)}...
                        </td>
                        <td className="p-3.5 text-right font-sans">
                          <button
                            type="button"
                            onClick={() => setInspectAuditLog(log)}
                            className="text-xs text-indigo-600 hover:text-indigo-900 font-semibold"
                          >
                            Metadata
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: TELEMETRY & CLOUDWATCH */}
      {activeTab === 'telemetry' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-slate-400 text-xs font-semibold">
                <span>HTTP Requests (1 hr)</span>
                <Server className="w-4 h-4 text-slate-600" />
              </div>
              <div className="text-3xl font-black text-slate-900">
                {telemetry ? Number(telemetry.metrics.http_requests_total || 0).toLocaleString() : '—'}
              </div>
              <p className="text-[11px] text-slate-500">Processed by ALB / Docker ASG</p>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-slate-400 text-xs font-semibold">
                <span>Database Latency</span>
                <Database className="w-4 h-4 text-slate-600" />
              </div>
              <div className="text-3xl font-black text-slate-900">
                {telemetry ? `${telemetry.metrics.db_latency_ms || 0} ms` : '—'}
              </div>
              <p className="text-[11px] text-slate-500">RDS PostgreSQL 16 Multi-AZ</p>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-slate-400 text-xs font-semibold">
                <span>5xx Error Count</span>
                <AlertTriangle className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-3xl font-black text-slate-900">
                {telemetry ? telemetry.metrics.http_5xx_errors ?? 0 : '0'}
              </div>
              <p className="text-[11px] text-emerald-600 font-semibold">Zero critical errors</p>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-slate-400 text-xs font-semibold">
                <span>Scans Dispatched</span>
                <Radio className="w-4 h-4 text-indigo-600" />
              </div>
              <div className="text-3xl font-black text-slate-900">
                {telemetry ? telemetry.metrics.scans_dispatched ?? 0 : '—'}
              </div>
              <p className="text-[11px] text-slate-500">Lambda Heuristic Scanner</p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-center justify-between">
            <span>Telemetry caching window: 60 seconds (CloudWatch degraded fallback safe).</span>
            <span className="font-mono text-slate-400">Source: AWS CloudWatch Logs & Metrics</span>
          </div>
        </div>
      )}

      {/* TAB 4: SCANNER HEURISTIC RULES */}
      {activeTab === 'rules' && (
        <div className="space-y-6">
          {scannerConfig && (
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm text-xs">
              <div>
                <span className="text-slate-400 font-semibold block">Ruleset Version</span>
                <span className="text-xl font-bold text-slate-900">Version {scannerConfig.ruleset_version}</span>
              </div>
              <div>
                <span className="text-slate-400 font-semibold block">High Priority Threshold</span>
                <span className="text-xl font-bold text-amber-600">{scannerConfig.high_priority_threshold} pts</span>
              </div>
              <div>
                <span className="text-slate-400 font-semibold block">Keyword Cap Points</span>
                <span className="text-xl font-bold text-slate-900">{scannerConfig.keyword_cap_points} pts</span>
              </div>
              <div>
                <span className="text-slate-400 font-semibold block">Prior Pending Points</span>
                <span className="text-xl font-bold text-slate-900">{scannerConfig.prior_pending_points} pts</span>
              </div>
            </div>
          )}

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-4 bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-700 uppercase">
              Active Heuristic Scanner Pattern Matching Rules
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-semibold">
                  <tr>
                    <th className="p-3.5">Pattern</th>
                    <th className="p-3.5">Rule Type</th>
                    <th className="p-3.5">Weight (Points)</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  {rules.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-8 text-center text-slate-400 font-sans">
                        No heuristic rules found.
                      </td>
                    </tr>
                  ) : (
                    rules.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-50/70">
                        <td className="p-3.5 font-bold text-slate-900 font-sans">{r.pattern}</td>
                        <td className="p-3.5">{r.rule_type}</td>
                        <td className="p-3.5 font-bold text-indigo-600">+{r.weight}</td>
                        <td className="p-3.5 font-sans">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                            {r.is_active ? 'ACTIVE' : 'DISABLED'}
                          </span>
                        </td>
                        <td className="p-3.5 text-slate-400 font-sans whitespace-nowrap">{formatDate(r.created_at)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Reject User Modal */}
      {rejectingUser && (
        <Modal
          isOpen={true}
          onClose={() => setRejectingUser(null)}
          title={`Reject Staff Application: ${rejectingUser.full_name}`}
        >
          <form onSubmit={handleConfirmReject} className="space-y-4">
            <p className="text-xs text-slate-600">
              Please enter the rationale explaining why this applicant did not meet agency clearance criteria:
            </p>

            <textarea
              required
              rows={3}
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:outline-slate-900"
            />

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={() => setRejectingUser(null)}>
                Cancel
              </Button>
              <Button type="submit" variant="danger">
                Confirm Rejection
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Edit Role Modal */}
      {roleChangeUser && (
        <Modal
          isOpen={true}
          onClose={() => setRoleChangeUser(null)}
          title={`Change Role: ${roleChangeUser.full_name}`}
        >
          <form onSubmit={handleConfirmRoleChange} className="space-y-4">
            <div>
              <label htmlFor="modal-role-select" className="block text-xs font-bold text-slate-700 uppercase mb-1">
                New Role Assignment
              </label>
              <select
                id="modal-role-select"
                value={selectedNewRole}
                onChange={(e) => setSelectedNewRole(e.target.value as UserRole)}
                className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:outline-slate-900 bg-white"
              >
                <option value="CITIZEN">CITIZEN</option>
                <option value="ANALYST">ANALYST (Triage & Intelligence)</option>
                <option value="EDUCATOR">EDUCATOR (CMS & Scenarios)</option>
                <option value="ADMIN">ADMIN (System Administrator)</option>
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={() => setRoleChangeUser(null)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary">
                Update Role
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Audit Log Metadata Modal */}
      {inspectAuditLog && (
        <Modal
          isOpen={true}
          onClose={() => setInspectAuditLog(null)}
          title={`Audit Event: ${inspectAuditLog.event_type}`}
        >
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div><strong className="text-slate-500">Event ID:</strong> <span className="font-mono">{inspectAuditLog.id}</span></div>
              <div><strong className="text-slate-500">Severity:</strong> <span className="font-bold">{inspectAuditLog.severity}</span></div>
              <div><strong className="text-slate-500">Actor:</strong> {inspectAuditLog.actor_email || inspectAuditLog.actor_id || 'System'}</div>
              <div><strong className="text-slate-500">Target:</strong> {inspectAuditLog.target_type} ({inspectAuditLog.target_id})</div>
            </div>

            <div className="space-y-1">
              <span className="font-bold text-slate-700 uppercase text-[10px]">Metadata Payload:</span>
              <pre className="p-3 bg-slate-900 text-slate-100 rounded-lg text-[11px] font-mono overflow-x-auto">
                {JSON.stringify(inspectAuditLog.metadata, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end pt-2">
              <Button size="sm" variant="outline" onClick={() => setInspectAuditLog(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
