import React, { useState, useEffect } from 'react';
import { reportsApi } from '../../api/reports';
import type { ScamReport } from '../../api/schema';
import { Button } from '../../components/Button';
import { FileText, PlusCircle } from 'lucide-react';
import { formatCurrency, formatDate } from '../../lib/format';
import { Link } from 'react-router-dom';

export const MyReportsPage: React.FC = () => {
  const [reports, setReports] = useState<ScamReport[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchReports = async () => {
    setIsLoading(true);
    try {
      const data = await reportsApi.getMyReports();
      setReports(data.results || []);
    } catch {
      setErrorMsg('Failed to load your submitted reports.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-4 py-12 space-y-6">
      <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <FileText className="w-6 h-6 text-slate-900" />
            <span>My Submitted Reports</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Track investigation progress and official review updates for reports linked to your account.
          </p>
        </div>

        <Link to="/report">
          <Button size="sm" leftIcon={<PlusCircle className="w-4 h-4" />}>
            New Incident Report
          </Button>
        </Link>
      </div>

      {errorMsg && (
        <div className="p-4 bg-red-50 text-red-700 text-sm rounded-lg border border-red-200">
          {errorMsg}
        </div>
      )}

      {/* Reports Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-sm text-slate-500">Loading your reports...</div>
        ) : reports.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <FileText className="w-10 h-10 text-slate-300 mx-auto" />
            <h2 className="text-sm font-bold text-slate-800">No reports submitted yet</h2>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              If you have been targeted by suspicious contacts or scams, report them to protect yourself and others.
            </p>
            <div className="pt-2">
              <Link to="/report">
                <Button size="sm" variant="outline">
                  Submit a Report
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-semibold">
                <tr>
                  <th className="p-3.5">Reference Code</th>
                  <th className="p-3.5">Category</th>
                  <th className="p-3.5">Reported Loss</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5">Submitted Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-sans">
                {reports.map((report) => (
                  <tr key={report.id} className="hover:bg-slate-50/70">
                    <td className="p-3.5 font-mono font-bold text-slate-900">{report.reference_code}</td>
                    <td className="p-3.5 text-slate-700 font-medium">{report.category}</td>
                    <td className="p-3.5 text-slate-600">
                      {formatCurrency(report.financial_loss, report.currency)}
                    </td>
                    <td className="p-3.5">
                      <span className={`px-2.5 py-0.5 rounded-full font-bold text-[10px] ${
                        report.status === 'VERIFIED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : report.status === 'REJECTED'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}>
                        {report.status}
                      </span>
                    </td>
                    <td className="p-3.5 text-slate-500">{formatDate(report.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
