import React, { useState } from 'react';
import { COPY } from '../../lib/copy';
import { Button } from '../../components/Button';
import { Input } from '../../components/Input';
import { Select } from '../../components/Select';
import { FileDrop } from '../../components/FileDrop';
import { Alert } from '../../components/Alert';
import { reportsApi } from '../../api/reports';
import type { CreateReportResponse, ScamCategory, PlatformType, PaymentMethod } from '../../api/schema';
import { parseApiError } from '../../api/errors';
import { ShieldCheck, Copy, Check, ArrowRight } from 'lucide-react';

export const ReportPage: React.FC = () => {
  const [step, setStep] = useState(1);
  const [category, setCategory] = useState<ScamCategory>('PHISHING');
  const [platform, setPlatform] = useState<PlatformType>('WHATSAPP');
  const [indicatorValue, setIndicatorValue] = useState('');
  const [financialLoss, setFinancialLoss] = useState('0');
  const [currency, setCurrency] = useState('MYR');
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('NONE');
  const [narrative, setNarrative] = useState('');
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [files, setFiles] = useState<File[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [submissionResult, setSubmissionResult] = useState<CreateReportResponse | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);

  const categoryOptions = [
    { value: 'PHISHING', label: 'Phishing / Fake Link' },
    { value: 'INVESTMENT', label: 'Investment Scam' },
    { value: 'E_COMMERCE', label: 'E-Commerce / Online Shopping' },
    { value: 'JOB', label: 'Job / Employment Offer' },
    { value: 'LOAN', label: 'Fake Loan' },
    { value: 'IMPERSONATION', label: 'Government / Authority Impersonation' },
    { value: 'LOVE_ROMANCE', label: 'Love / Romance Scam' },
    { value: 'OTHER', label: 'Other Fraud' },
  ];

  const platformOptions = [
    { value: 'WHATSAPP', label: 'WhatsApp' },
    { value: 'TELEGRAM', label: 'Telegram' },
    { value: 'SMS', label: 'SMS / Text Message' },
    { value: 'FACEBOOK', label: 'Facebook' },
    { value: 'INSTAGRAM', label: 'Instagram' },
    { value: 'TIKTOK', label: 'TikTok' },
    { value: 'EMAIL', label: 'Email' },
    { value: 'PHONE_CALL', label: 'Phone Call' },
    { value: 'WEBSITE', label: 'Direct Website / URL' },
    { value: 'OTHER', label: 'Other Platform' },
  ];

  const paymentOptions = [
    { value: 'NONE', label: 'No Financial Loss / Did Not Pay' },
    { value: 'BANK_TRANSFER', label: 'Direct Bank Transfer' },
    { value: 'CREDIT_DEBIT_CARD', label: 'Credit / Debit Card' },
    { value: 'E_WALLET', label: 'E-Wallet (Touch n Go, Grab, etc.)' },
    { value: 'CRYPTOCURRENCY', label: 'Cryptocurrency' },
    { value: 'GIFT_CARD', label: 'Gift Card / Reload Pin' },
    { value: 'CASH', label: 'Cash' },
  ];

  const currencyOptions = [
    { value: 'MYR', label: 'MYR (Malaysian Ringgit)' },
    { value: 'NPR', label: 'NPR (Nepalese Rupee)' },
    { value: 'USD', label: 'USD (US Dollar)' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);

    try {
      const formData = new FormData();
      formData.append('category', category);
      formData.append('platform', platform);
      formData.append('message_text', narrative);
      formData.append('financial_loss', financialLoss || '0');
      formData.append('currency', currency);
      formData.append('payment_method', paymentMethod);
      formData.append('is_anonymous', String(isAnonymous));

      if (indicatorValue.trim()) {
        formData.append(
          'indicators',
          JSON.stringify([
            {
              indicator_type: indicatorValue.startsWith('http') ? 'URL' : 'PHONE',
              raw_value: indicatorValue.trim(),
            },
          ])
        );
      }

      files.forEach((f) => {
        formData.append('evidence', f);
      });

      // Generate Idempotency UUID
      const idempotencyKey = crypto.randomUUID();
      const res = await reportsApi.createReport(formData, idempotencyKey);
      setSubmissionResult(res);
    } catch (err) {
      const parsed = parseApiError(err);
      setErrorMsg(parsed.message || 'Report submission failed. Please review your input.');
    } finally {
      setIsLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  if (submissionResult) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12 space-y-8">
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-md space-y-6">
          <div className="flex items-center gap-3 text-emerald-600">
            <ShieldCheck className="w-8 h-8" />
            <h1 className="text-2xl font-bold text-slate-900">Incident Report Submitted</h1>
          </div>

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-3">
            <div className="flex justify-between items-center text-sm">
              <span className="font-semibold text-slate-700">Reference Code:</span>
              <strong className="font-mono text-base text-slate-900 bg-white px-3 py-1 rounded border border-slate-200">
                {submissionResult.reference_code}
              </strong>
            </div>

            {submissionResult.access_key && (
              <div className="flex justify-between items-center text-sm pt-2 border-t border-slate-200">
                <div>
                  <span className="font-semibold text-slate-700 block">Anonymous Access Key:</span>
                  <span className="text-xs text-red-600">Save this now! It cannot be retrieved later.</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="bg-amber-100 text-amber-900 px-3 py-1 rounded font-mono text-xs">
                    {submissionResult.access_key}
                  </code>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(submissionResult.access_key!)}
                    className="p-1.5 rounded hover:bg-slate-200 text-slate-600"
                    title="Copy Access Key"
                  >
                    {copiedKey ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Personalized Recovery Playbook */}
          {submissionResult.playbook && (
            <div className="space-y-4 pt-4 border-t border-slate-100">
              <h2 className="text-lg font-bold text-slate-900">
                {submissionResult.playbook.title || 'Recommended Immediate Actions'}
              </h2>
              <div className="space-y-3">
                {submissionResult.playbook.steps?.map((stepItem, idx) => (
                  <div key={idx} className="p-4 rounded-lg bg-blue-50 border border-blue-100 text-sm">
                    <h3 className="font-bold text-blue-950">{stepItem.title}</h3>
                    <p className="text-slate-700 mt-1">{stepItem.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="pt-4 flex justify-end">
            <Button onClick={() => window.location.reload()}>
              Submit Another Report
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-12 space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold text-slate-900">{COPY.report.title}</h1>
        <p className="text-slate-600">{COPY.report.subtitle}</p>
      </div>

      <div className="bg-white p-6 sm:p-8 rounded-xl border border-slate-200 shadow-sm space-y-6">
        {errorMsg && (
          <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}

        <div className="flex items-center justify-between border-b border-slate-100 pb-4 text-xs font-semibold text-slate-400">
          <span className={step >= 1 ? 'text-slate-900 font-bold' : ''}>1. Scam Details</span>
          <ArrowRight className="w-3.5 h-3.5" />
          <span className={step >= 2 ? 'text-slate-900 font-bold' : ''}>2. Loss & Evidence</span>
          <ArrowRight className="w-3.5 h-3.5" />
          <span className={step >= 3 ? 'text-slate-900 font-bold' : ''}>3. Narrative</span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {step === 1 && (
            <div className="space-y-4">
              <Select
                id="report-category"
                label={COPY.report.categoryLabel}
                value={category}
                onChange={(e) => setCategory(e.target.value as ScamCategory)}
                options={categoryOptions}
              />

              <Select
                id="report-platform"
                label={COPY.report.platformLabel}
                value={platform}
                onChange={(e) => setPlatform(e.target.value as PlatformType)}
                options={platformOptions}
              />

              <Input
                id="report-indicator"
                label="Offender Contact (Phone Number, Website, or Account)"
                placeholder="e.g. +6012-345-6789 or https://fake-deal.com"
                value={indicatorValue}
                onChange={(e) => setIndicatorValue(e.target.value)}
              />

              <div className="flex justify-end pt-4">
                <Button onClick={() => setStep(2)}>Next: Loss & Evidence</Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  id="report-loss"
                  type="number"
                  label={COPY.report.lossLabel}
                  value={financialLoss}
                  onChange={(e) => setFinancialLoss(e.target.value)}
                  min="0"
                  step="0.01"
                />

                <Select
                  id="report-currency"
                  label={COPY.report.currencyLabel}
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  options={currencyOptions}
                />
              </div>

              <Select
                id="report-payment"
                label="Payment Method Used"
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
                options={paymentOptions}
              />

              <div className="pt-2">
                <label className="block text-sm font-semibold text-slate-800 mb-1.5">
                  {COPY.report.evidenceUploadLabel}
                </label>
                <FileDrop files={files} onFilesChange={setFiles} />
              </div>

              <div className="flex justify-between pt-4">
                <Button variant="secondary" onClick={() => setStep(1)}>
                  Back
                </Button>
                <Button onClick={() => setStep(3)}>Next: Narrative</Button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="report-narrative" className="block text-sm font-semibold text-slate-800">
                  {COPY.report.narrativeLabel} <span className="text-red-600">*</span>
                </label>
                <textarea
                  id="report-narrative"
                  required
                  rows={4}
                  className="w-full rounded-md border border-slate-300 p-3 text-sm focus-visible:outline focus-visible:outline-slate-900"
                  placeholder={COPY.report.narrativePlaceholder}
                  value={narrative}
                  onChange={(e) => setNarrative(e.target.value)}
                />
              </div>

              <div className="flex items-center gap-2 p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <input
                  id="anon-check"
                  type="checkbox"
                  checked={isAnonymous}
                  onChange={(e) => setIsAnonymous(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                />
                <label htmlFor="anon-check" className="text-xs font-medium text-slate-700 cursor-pointer">
                  {COPY.report.anonymousToggle}
                </label>
              </div>

              <div className="flex justify-between pt-4">
                <Button variant="secondary" onClick={() => setStep(2)}>
                  Back
                </Button>
                <Button type="submit" isLoading={isLoading}>
                  {COPY.report.submitReport}
                </Button>
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};
