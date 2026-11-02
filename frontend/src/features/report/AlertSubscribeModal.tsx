import React, { useState } from 'react';
import { Modal } from '../../components/Modal';
import { Input } from '../../components/Input';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import { apiClient } from '../../api/client';
import { parseApiError } from '../../api/errors';
import { BellRing, CheckCircle2 } from 'lucide-react';

export interface AlertSubscribeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AlertSubscribeModal: React.FC<AlertSubscribeModalProps> = ({ isOpen, onClose }) => {
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [audienceGroup, setAudienceGroup] = useState('GENERAL');
  const [enableSms, setEnableSms] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubscribe = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);

    try {
      await apiClient.post('/alerts/subscriptions/', {
        email: email.trim(),
        phone_number: enableSms ? phone.trim() : null,
        sms_enabled: enableSms,
        audience_group: audienceGroup,
        categories: ['PHISHING', 'INVESTMENT', 'IMPERSONATION'],
      });

      setIsSuccess(true);
    } catch (err) {
      const parsed = parseApiError(err);
      setErrorMsg(parsed.message || 'Subscription failed. Please check your contact information.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setIsSuccess(false);
    setErrorMsg(null);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Subscribe to Threat Intelligence Alerts"
    >
      {isSuccess ? (
        <div className="py-6 text-center space-y-4">
          <div className="p-3 bg-emerald-100 text-emerald-700 rounded-full w-fit mx-auto">
            <CheckCircle2 className="w-10 h-10" />
          </div>
          <h3 className="text-lg font-bold text-slate-900">Subscription Registered</h3>
          <p className="text-xs text-slate-600 max-w-sm mx-auto leading-relaxed">
            A confirmation link has been sent to <strong>{email}</strong>. Please click the link in your email to activate alert broadcasts.
          </p>
          <div className="pt-2">
            <Button onClick={handleClose}>Done</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubscribe} className="space-y-4">
          {errorMsg && (
            <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
              {errorMsg}
            </Alert>
          )}

          <p className="text-xs text-slate-600 leading-relaxed">
            Receive verified high-priority scam advisories issued by national fraud analysts.
          </p>

          <Input
            id="sub-email"
            type="email"
            label="Email Address"
            required
            placeholder="citizen@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <div className="space-y-2">
            <label className="block text-sm font-semibold text-slate-800">
              Target Audience Focus
            </label>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {[
                { value: 'GENERAL', label: 'General Alerts' },
                { value: 'ELDERLY', label: 'Seniors & Families' },
                { value: 'TEENAGER', label: 'Youth & Gaming' },
                { value: 'NON_TECH', label: 'Non-Technical' },
              ].map((grp) => (
                <button
                  key={grp.value}
                  type="button"
                  onClick={() => setAudienceGroup(grp.value)}
                  className={`p-2 rounded-lg border text-left font-medium transition-colors ${
                    audienceGroup === grp.value
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {grp.label}
                </button>
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 space-y-3">
            <div className="flex items-center gap-2">
              <input
                id="sms-toggle"
                type="checkbox"
                checked={enableSms}
                onChange={(e) => setEnableSms(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
              />
              <label htmlFor="sms-toggle" className="text-xs font-semibold text-slate-700 cursor-pointer">
                Also receive critical SMS alerts
              </label>
            </div>

            {enableSms && (
              <Input
                id="sub-phone"
                type="tel"
                label="Mobile Phone (+60 / +977)"
                required={enableSms}
                placeholder="+60 12-345-6789"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            )}
          </div>

          <div className="pt-4 flex justify-end gap-2 border-t border-slate-100">
            <Button variant="secondary" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isLoading} leftIcon={<BellRing className="w-4 h-4" />}>
              Subscribe
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
};
