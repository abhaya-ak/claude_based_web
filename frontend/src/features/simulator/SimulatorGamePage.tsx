import React, { useState } from 'react';
import { COPY } from '../../lib/copy';
import { Button } from '../../components/Button';
import { Target, CheckCircle2, XCircle, ArrowRight } from 'lucide-react';

interface MockScenario {
  id: string;
  title: string;
  sender: string;
  message: string;
  tactic: string;
  isScam: boolean;
  explanation: string;
}

const DEMO_SCENARIOS: MockScenario[] = [
  {
    id: 'sc-1',
    title: 'Urgent Bank Account Suspension SMS',
    sender: '+6011-2345-9876',
    message: 'URGENT: Your Maybank2u session is locked due to suspicious activity. Verify immediately at https://myb-verify.top/login or your account will be frozen permanently.',
    tactic: 'URGENCY',
    isScam: true,
    explanation: 'Banks never send urgent threats of account suspension containing non-official domain links (.top, .xyz).',
  },
  {
    id: 'sc-2',
    title: 'Government Tax Refund Notification',
    sender: 'LHDN Official Alert',
    message: 'LHDN Malaysia: You have an unclaimed tax surplus of RM850.00. Click to claim into your account: https://lhdn-surplus-portal.com',
    tactic: 'AUTHORITY',
    isScam: true,
    explanation: 'Official tax agencies disburse refunds directly through registered accounts, never via unverified third-party SMS links.',
  },
  {
    id: 'sc-3',
    title: 'Legitimate Two-Factor OTP Code',
    sender: 'SECURE-AUTH',
    message: 'Your verification security code is 849201. Valid for 5 minutes. Do not share this code with anyone, including customer service.',
    tactic: 'NONE',
    isScam: false,
    explanation: 'This is a standard system 2FA code that contains no hyperlinks, requests no credentials, and warns against sharing.',
  },
];

export const SimulatorGamePage: React.FC = () => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [isCompleted, setIsCompleted] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);

  const currentScenario = DEMO_SCENARIOS[currentIndex];

  const handleDecision = (userMarkedScam: boolean) => {
    setAnswers({ ...answers, [currentScenario.id]: userMarkedScam });
    setShowFeedback(true);
  };

  const handleNext = () => {
    setShowFeedback(false);
    if (currentIndex + 1 < DEMO_SCENARIOS.length) {
      setCurrentIndex(currentIndex + 1);
    } else {
      setIsCompleted(true);
    }
  };

  const calculateScore = () => {
    let correct = 0;
    DEMO_SCENARIOS.forEach((sc) => {
      if (answers[sc.id] === sc.isScam) correct += 1;
    });
    return {
      correct,
      total: DEMO_SCENARIOS.length,
      pct: Math.round((correct / DEMO_SCENARIOS.length) * 100),
    };
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-12 space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold text-slate-900">{COPY.simulator.title}</h1>
        <p className="text-slate-600">{COPY.simulator.subtitle}</p>
      </div>

      {!isCompleted ? (
        <div className="bg-white p-6 sm:p-8 rounded-xl border border-slate-200 shadow-sm space-y-6">
          <div className="flex justify-between items-center border-b border-slate-100 pb-4 text-xs font-semibold text-slate-500">
            <span>Scenario {currentIndex + 1} of {DEMO_SCENARIOS.length}</span>
            <span className="px-2.5 py-0.5 rounded bg-amber-100 text-amber-800 font-bold">
              Practice Round
            </span>
          </div>

          {/* Scenario Mock Message Screen */}
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-slate-900">{currentScenario.title}</h2>

            <div className="rounded-xl border border-slate-200 bg-slate-900 text-slate-100 p-5 shadow-inner space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between text-slate-400 border-b border-slate-800 pb-2">
                <span>Sender: {currentScenario.sender}</span>
                <span>Incoming SMS</span>
              </div>
              <p className="text-sm text-white leading-relaxed font-sans">{currentScenario.message}</p>
            </div>
          </div>

          {/* Decision Controls */}
          {!showFeedback ? (
            <div className="space-y-3 pt-2">
              <p className="text-sm font-semibold text-slate-800 text-center">
                {COPY.simulator.decisionPrompt}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Button
                  variant="danger"
                  size="lg"
                  onClick={() => handleDecision(true)}
                >
                  {COPY.simulator.yesScam}
                </Button>
                <Button
                  variant="secondary"
                  size="lg"
                  onClick={() => handleDecision(false)}
                >
                  {COPY.simulator.noLegit}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4 pt-2 border-t border-slate-100">
              <div className={`p-4 rounded-lg text-sm flex items-start gap-3 ${
                answers[currentScenario.id] === currentScenario.isScam
                  ? 'bg-emerald-50 text-emerald-900 border border-emerald-200'
                  : 'bg-red-50 text-red-900 border border-red-200'
              }`}>
                {answers[currentScenario.id] === currentScenario.isScam ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                )}
                <div className="space-y-1">
                  <p className="font-bold">
                    {answers[currentScenario.id] === currentScenario.isScam
                      ? 'Correct Decision!'
                      : 'Incorrect Assessment'}
                  </p>
                  <p className="text-xs text-slate-700 leading-relaxed">{currentScenario.explanation}</p>
                </div>
              </div>

              <div className="flex justify-end">
                <Button onClick={handleNext} rightIcon={<ArrowRight className="w-4 h-4" />}>
                  {currentIndex + 1 < DEMO_SCENARIOS.length ? 'Next Scenario' : 'View Results'}
                </Button>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Results Card */
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-md text-center space-y-6">
          <div className="inline-flex p-4 rounded-full bg-slate-900 text-white">
            <Target className="w-10 h-10" />
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-slate-900">Training Exercise Complete</h2>
            <div className="text-4xl font-extrabold text-slate-900">
              {calculateScore().pct}%
            </div>
            <p className="text-xs text-slate-500">
              Score: {calculateScore().correct} of {calculateScore().total} scenarios identified accurately
            </p>
          </div>

          <div className="pt-4 flex justify-center">
            <Button onClick={() => {
              setCurrentIndex(0);
              setAnswers({});
              setIsCompleted(false);
            }}>
              Restart Exercise
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
