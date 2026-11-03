import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthProvider';
import { COPY } from '../../lib/copy';
import { Button } from '../../components/Button';
import { Input } from '../../components/Input';
import { Select } from '../../components/Select';
import { FileDrop } from '../../components/FileDrop';
import { Alert } from '../../components/Alert';
import { reportsApi, type ReportOptions } from '../../api/reports';
import type { ScamCategory, PlatformType, PaymentMethod } from '../../api/schema';
import { parseApiError } from '../../api/errors';
import { ArrowRight, ArrowLeft } from 'lucide-react';

export const ReportWizard: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const [step, setStep] = useState(1);
  const [options, setOptions] = useState<ReportOptions | null>(null);

  // Form Fields
  const [category, setCategory] = useState<ScamCategory>('PHISHING');
  const [platform, setPlatform] = useState<PlatformType>('WHATSAPP');
  const [indicatorType, setIndicatorType] = useState<'PHONE' | 'URL' | 'BANK_ACCOUNT' | 'EMAIL'>('PHONE');
  const [indicatorValue, setIndicatorValue] = useState('');
  const [financialLoss, setFinancialLoss] = useState('0');
  const [currency, setCurrency] = useState('MYR');
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('NONE');
  const [narrative, setNarrative] = useState('');
  const [isAnonymous, setIsAnonymous] = useState(!isAuthenticated);
  const [files, setFiles] = useState<File[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    reportsApi
      .getOptions()
      .then((data) => setOptions(data))
      .catch(() => {
        // Fallback default options
      });
  }, []);

  const defaultCategories = [
    { value: 'PHISHING', label: 'Phishing / Fake Link' },
    { value: 'INVESTMENT', label: 'Investment Fraud' },
    { value: 'E_COMMERCE', label: 'E-Commerce / Shopping Scam' },
    { value: 'JOB', label: 'Fake Job / Task Scam' },
    { value: 'LOAN', label: 'Fake Loan' },
    { value: 'IMPERSONATION', label: 'Government Impersonation' },
    { value: 'LOVE_ROMANCE', label: 'Love / Romance Scam' },
    { value: 'OTHER', label: 'Other Fraud Type' },
  ];

  const defaultPlatforms = [
    { value: 'WHATSAPP', label: 'WhatsApp' },
    { value: 'TELEGRAM', label: 'Telegram' },
    { value: 'SMS', label: 'SMS / Text Message' },
    { value: 'FACEBOOK', label: 'Facebook' },
    { value: 'INSTAGRAM', label: 'Instagram' },
    { value: 'TIKTOK', label: 'TikTok' },
    { value: 'EMAIL', label: 'Email' },
    { value: 'PHONE_CALL', label: 'Phone Call' },
    { value: 'WEBSITE', label: 'Direct Website' },
    { value: 'OTHER', label: 'Other Platform' },
  ];

  const defaultPaymentMethods = [
    { value: 'NONE', label: 'No Financial Loss' },
    { value: 'BANK_TRANSFER', label: 'Direct Bank Transfer' },
    { value: 'CREDIT_DEBIT_CARD', label: 'Credit / Debit Card' },
    { value: 'E_WALLET', label: 'E-Wallet (Touch n Go / Grab)' },
    { value: 'CRYPTOCURRENCY', label: 'Cryptocurrency' },
    { value: 'GIFT_CARD', label: 'Gift Card / Pin' },
    { value: 'CASH', label: 'Cash' },
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
              indicator_type: indicatorType,
              raw_value: indicatorValue.trim(),
            },
          ])
        );
      }

      files.forEach((file) => {
        formData.append('evidence', file);
      });

      // Strict client-side idempotency UUID key
      const idempotencyKey = crypto.randomUUID();
      const response = await reportsApi.createReport(formData, idempotencyKey);

      navigate('/report/success', { state: { report: response } });
    } catch (err) {
      const parsed = parseApiError(err);
      setErrorMsg(parsed.message || 'Report submission failed. Please check your inputs.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-12 space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold text-slate-900">{COPY.report.title}</h1>
        <p className="text-slate-600 text-sm">{COPY.report.subtitle}</p>
      </div>

      <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-sm space-y-6">
        {errorMsg && (
          <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
            {errorMsg}
          </Alert>
        )}

        {/* Wizard Step Progression Bar */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4 text-xs font-semibold text-slate-400">
          <span className={step >= 1 ? 'text-slate-900 font-bold' : ''}>1. Classification</span>
          <ArrowRight className="w-3.5 h-3.5" />
          <span className={step >= 2 ? 'text-slate-900 font-bold' : ''}>2. Offender Contact</span>
          <ArrowRight className="w-3.5 h-3.5" />
          <span className={step >= 3 ? 'text-slate-900 font-bold' : ''}>3. Financial Loss</span>
          <ArrowRight className="w-3.5 h-3.5" />
          <span className={step >= 4 ? 'text-slate-900 font-bold' : ''}>4. Narrative & Proof</span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Step 1: Classification */}
          {step === 1 && (
            <div className="space-y-4">
              <Select
                id="wizard-category"
                label={COPY.report.categoryLabel}
                value={category}
                onChange={(e) => setCategory(e.target.value as ScamCategory)}
                options={options?.categories || defaultCategories}
              />

              <Select
                id="wizard-platform"
                label={COPY.report.platformLabel}
                value={platform}
                onChange={(e) => setPlatform(e.target.value as PlatformType)}
                options={options?.platforms || defaultPlatforms}
              />

              <div className="flex justify-end pt-4">
                <Button onClick={() => setStep(2)} rightIcon={<ArrowRight className="w-4 h-4" />}>
                  Next: Offender Details
                </Button>
              </div>
            </div>
          )}

          {/* Step 2: Offender Contact Indicators */}
          {step === 2 && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <Select
                  id="wizard-indicator-type"
                  label="Contact Type"
                  value={indicatorType}
                  onChange={(e) =>
                    setIndicatorType(e.target.value as 'PHONE' | 'URL' | 'BANK_ACCOUNT' | 'EMAIL')
                  }
                  options={[
                    { value: 'PHONE', label: 'Phone Number' },
                    { value: 'URL', label: 'Website / Link' },
                    { value: 'BANK_ACCOUNT', label: 'Bank Account' },
                    { value: 'EMAIL', label: 'Email Address' },
                  ]}
                />

                <div className="sm:col-span-2">
                  <Input
                    id="wizard-indicator-val"
                    label="Offender Detail / Value"
                    placeholder={
                      indicatorType === 'PHONE'
                        ? '+60 12-345-6789'
                        : indicatorType === 'URL'
                        ? 'https://malicious-login.top'
                        : indicatorType === 'BANK_ACCOUNT'
                        ? 'Account digits (e.g. 114012345678)'
                        : 'scammer@fake-agent.com'
                    }
                    value={indicatorValue}
                    onChange={(e) => setIndicatorValue(e.target.value)}
                  />
                </div>
              </div>

              <div className="flex justify-between pt-4">
                <Button variant="secondary" onClick={() => setStep(1)} leftIcon={<ArrowLeft className="w-4 h-4" />}>
                  Back
                </Button>
                <Button onClick={() => setStep(3)} rightIcon={<ArrowRight className="w-4 h-4" />}>
                  Next: Financial Loss
                </Button>
              </div>
            </div>
          )}

          {/* Step 3: Financial Loss & Payment Method */}
          {step === 3 && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  id="wizard-loss"
                  type="number"
                  label={COPY.report.lossLabel}
                  value={financialLoss}
                  onChange={(e) => setFinancialLoss(e.target.value)}
                  min="0"
                  step="0.01"
                />

                <Select
                  id="wizard-currency"
                  label={COPY.report.currencyLabel}
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  options={[
                    { value: 'MYR', label: 'MYR (Malaysian Ringgit)' },
                    { value: 'NPR', label: 'NPR (Nepalese Rupee)' },
                    { value: 'USD', label: 'USD (US Dollar)' },
                  ]}
                />
              </div>

              <Select
                id="wizard-payment"
                label="Payment Method"
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
                options={options?.payment_methods || defaultPaymentMethods}
              />

              <div className="flex justify-between pt-4">
                <Button variant="secondary" onClick={() => setStep(2)} leftIcon={<ArrowLeft className="w-4 h-4" />}>
                  Back
                </Button>
                <Button onClick={() => setStep(4)} rightIcon={<ArrowRight className="w-4 h-4" />}>
                  Next: Narrative & Proof
                </Button>
              </div>
            </div>
          )}

          {/* Step 4: Narrative & FileDrop */}
          {step === 4 && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="wizard-narrative" className="block text-sm font-semibold text-slate-800">
                  {COPY.report.narrativeLabel} <span className="text-red-600">*</span>
                </label>
                <textarea
                  id="wizard-narrative"
                  required
                  rows={4}
                  className="w-full rounded-md border border-slate-300 p-3 text-sm focus-visible:outline focus-visible:outline-slate-900"
                  placeholder={COPY.report.narrativePlaceholder}
                  value={narrative}
                  onChange={(e) => setNarrative(e.target.value)}
                />
              </div>

              <div className="pt-2">
                <label className="block text-sm font-semibold text-slate-800 mb-1.5">
                  {COPY.report.evidenceUploadLabel}
                </label>
                <FileDrop files={files} onFilesChange={setFiles} />
              </div>

              {/* Anonymous Checkbox */}
              <div className="flex items-center gap-2 p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <input
                  id="wizard-anon"
                  type="checkbox"
                  checked={isAnonymous}
                  disabled={!isAuthenticated}
                  onChange={(e) => setIsAnonymous(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                />
                <label htmlFor="wizard-anon" className="text-xs font-medium text-slate-700 cursor-pointer">
                  {COPY.report.anonymousToggle}
                  {!isAuthenticated && ' (Default for guest submissions)'}
                </label>
              </div>

              <div className="flex justify-between pt-4">
                <Button variant="secondary" onClick={() => setStep(3)} leftIcon={<ArrowLeft className="w-4 h-4" />}>
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
