import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { COPY } from '../../lib/copy';
import { literacyApi } from '../../api/literacy';
import type {
  SimulatorScenario,
  AnswerFeedbackResponse,
  SimulatorAttemptCompletionResponse,
} from '../../api/schema';
import { Button } from '../../components/Button';
import { Alert } from '../../components/Alert';
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  ArrowRight,
  RotateCcw,
  BookOpen,
  Award,
  AlertTriangle,
  Play,
  Layers,
} from 'lucide-react';

export const SimulatorGamePage: React.FC = () => {
  const [gameState, setGameState] = useState<'IDLE' | 'PLAYING' | 'FEEDBACK' | 'COMPLETED'>('IDLE');
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [sessionKey, setSessionKey] = useState<string | undefined>(undefined);
  const [scenarios, setScenarios] = useState<SimulatorScenario[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  const [feedback, setFeedback] = useState<AnswerFeedbackResponse | null>(null);
  const [completionResult, setCompletionResult] = useState<SimulatorAttemptCompletionResponse | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleStartGame = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await literacyApi.startAttempt();
      setAttemptId(data.attempt_id);
      setSessionKey(data.session_key);
      setScenarios(data.scenarios || []);
      setCurrentIndex(0);
      setFeedback(null);
      setCompletionResult(null);
      setGameState('PLAYING');
    } catch {
      setErrorMsg('Failed to initialize simulation round. Please verify network connectivity.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDecision = async (userMarkedScam: boolean) => {
    if (!attemptId || scenarios.length === 0) return;
    const currentScenario = scenarios[currentIndex];

    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await literacyApi.submitAnswer(attemptId, {
        scenario_id: currentScenario.id,
        answered_is_scam: userMarkedScam,
        session_key: sessionKey,
      });
      setFeedback(res);
      setGameState('FEEDBACK');
    } catch {
      setErrorMsg('Failed to submit answer.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleNextScenario = async () => {
    if (!attemptId) return;

    if (currentIndex + 1 < scenarios.length) {
      setCurrentIndex((prev) => prev + 1);
      setFeedback(null);
      setGameState('PLAYING');
    } else {
      // Completed last scenario -> Finalize Attempt
      setIsLoading(true);
      try {
        const result = await literacyApi.completeAttempt(attemptId, sessionKey);
        setCompletionResult(result);
        setGameState('COMPLETED');
      } catch {
        setErrorMsg('Failed to generate simulation final score.');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const currentScenario = scenarios[currentIndex];

  return (
    <div className="max-w-4xl mx-auto px-4 py-12 space-y-8">
      {/* Title Header */}
      <div className="text-center space-y-2">
        <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight flex items-center justify-center gap-2">
          <ShieldAlert className="w-8 h-8 text-amber-500" />
          <span>{COPY.simulator.title}</span>
        </h1>
        <p className="text-sm text-slate-600 max-w-xl mx-auto">
          {COPY.simulator.subtitle}
        </p>
      </div>

      {errorMsg && (
        <Alert variant="error" onDismiss={() => setErrorMsg(null)}>
          {errorMsg}
        </Alert>
      )}

      {/* State 1: IDLE / Welcome Screen */}
      {gameState === 'IDLE' && (
        <div className="bg-white p-8 sm:p-12 rounded-2xl border border-slate-200 shadow-sm text-center space-y-6">
          <div className="w-16 h-16 rounded-full bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mx-auto">
            <Layers className="w-8 h-8" />
          </div>

          <div className="space-y-2 max-w-lg mx-auto">
            <h2 className="text-xl font-bold text-slate-900">Interactive Scam Defense Training</h2>
            <p className="text-xs text-slate-600 leading-relaxed">
              Test your ability to spot deceptive psychological tactics across authentic email, SMS, and messaging scenarios.
              Your answers are scored server-side with anti-cheat protection.
            </p>
          </div>

          <div className="pt-2">
            <Button
              size="lg"
              variant="primary"
              onClick={handleStartGame}
              isLoading={isLoading}
              leftIcon={<Play className="w-5 h-5 fill-current" />}
            >
              Start Simulation Round
            </Button>
          </div>
        </div>
      )}

      {/* State 2 & 3: PLAYING or FEEDBACK Card */}
      {(gameState === 'PLAYING' || gameState === 'FEEDBACK') && currentScenario && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-md overflow-hidden space-y-6 p-6 sm:p-8">
          {/* Progress Header */}
          <div className="flex items-center justify-between border-b border-slate-100 pb-4 text-xs font-semibold text-slate-500">
            <span>
              Scenario {currentIndex + 1} of {scenarios.length}
            </span>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded bg-slate-100 text-slate-700 uppercase text-[10px] font-bold">
                Channel: {currentScenario.channel || 'INCOMING'}
              </span>
              <span className="px-2.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-bold">
                Level {currentScenario.difficulty || 1}
              </span>
            </div>
          </div>

          {/* Scenario Content / Image */}
          <div className="space-y-4">
            <h2 className="text-xl font-black text-slate-900">{currentScenario.title}</h2>

            <div className="bg-slate-900 text-slate-100 rounded-xl p-5 shadow-inner border border-slate-800 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between text-slate-400 border-b border-slate-800 pb-2">
                <span>Message Simulation</span>
                <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded">AUTHENTIC INTERCEPT</span>
              </div>
              <p className="font-sans text-sm text-slate-100 whitespace-pre-wrap leading-relaxed">
                {currentScenario.image_alt || 'Examine this simulated interaction for psychological manipulation or spoofed details.'}
              </p>
            </div>
          </div>

          {/* Decision Buttons (PLAYING Mode) */}
          {gameState === 'PLAYING' && (
            <div className="space-y-4 pt-4 border-t border-slate-100">
              <p className="text-center text-xs font-bold uppercase tracking-wider text-slate-500">
                Is this message a scam or legitimate communication?
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Button
                  size="lg"
                  variant="danger"
                  onClick={() => handleDecision(true)}
                  isLoading={isLoading}
                  leftIcon={<ShieldAlert className="w-5 h-5" />}
                >
                  Flag as Scam
                </Button>
                <Button
                  size="lg"
                  variant="secondary"
                  onClick={() => handleDecision(false)}
                  isLoading={isLoading}
                  leftIcon={<CheckCircle2 className="w-5 h-5 text-emerald-600" />}
                >
                  Mark as Legitimate / Safe
                </Button>
              </div>
            </div>
          )}

          {/* Feedback Display (FEEDBACK Mode) */}
          {gameState === 'FEEDBACK' && feedback && (
            <div className="space-y-5 pt-4 border-t border-slate-100">
              <div
                className={`p-5 rounded-xl border flex items-start gap-3.5 ${
                  feedback.is_correct
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-950'
                    : 'bg-red-50 border-red-200 text-red-950'
                }`}
              >
                {feedback.is_correct ? (
                  <CheckCircle2 className="w-6 h-6 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <XCircle className="w-6 h-6 text-red-600 shrink-0 mt-0.5" />
                )}
                <div className="space-y-1 text-xs">
                  <strong className="block text-sm font-black">
                    {feedback.is_correct ? 'Correct Decision!' : 'Incorrect Assessment'}
                  </strong>
                  <p className="leading-relaxed text-slate-800">{feedback.explanation}</p>
                </div>
              </div>

              {/* Red Flag Hotspots Details */}
              {feedback.red_flags && feedback.red_flags.length > 0 && (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2 text-xs">
                  <div className="font-bold text-slate-700 flex items-center gap-1.5 uppercase tracking-wider text-[10px]">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    <span>Identified Red Flags & Deception Tactics:</span>
                  </div>
                  <ul className="list-disc pl-5 space-y-1 text-slate-600">
                    {feedback.red_flags.map((flag, idx) => (
                      <li key={idx}>
                        <strong>[{flag.flag_code || 'TACTIC'}]:</strong> {flag.explanation}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex justify-end pt-2">
                <Button
                  size="md"
                  variant="primary"
                  onClick={handleNextScenario}
                  isLoading={isLoading}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  {currentIndex + 1 < scenarios.length ? 'Next Scenario' : 'View Results & Breakdown'}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* State 4: COMPLETED Screen */}
      {gameState === 'COMPLETED' && completionResult && (
        <div className="bg-white p-8 sm:p-12 rounded-2xl border border-slate-200 shadow-md space-y-8">
          <div className="text-center space-y-3">
            <div className="w-16 h-16 rounded-full bg-slate-900 text-amber-400 flex items-center justify-center mx-auto shadow-md">
              <Award className="w-9 h-9" />
            </div>

            <h2 className="text-2xl font-black text-slate-900">Training Exercise Complete</h2>
            <div className="text-5xl font-black text-slate-900 tracking-tight">
              {completionResult.score_pct}%
            </div>
            <p className="text-xs text-slate-500">
              You correctly assessed {completionResult.profile.correct_scenarios} of {completionResult.profile.total_scenarios} scenarios.
            </p>
          </div>

          {/* Blind Spots Notification */}
          {completionResult.profile.blind_spots && completionResult.profile.blind_spots.length > 0 && (
            <div className="p-5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-2">
              <div className="font-bold flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>Identified Blind Spots:</span>
              </div>
              <p className="leading-relaxed">
                You missed multiple scenarios involving the following psychological manipulation tactics:
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                {completionResult.profile.blind_spots.map((spot) => (
                  <span
                    key={spot}
                    className="px-3 py-1 rounded-full font-bold bg-amber-200/60 text-amber-950 border border-amber-300"
                  >
                    {spot}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Remediation Guides Section */}
          {completionResult.remediation_guides && completionResult.remediation_guides.length > 0 && (
            <div className="space-y-4 pt-4 border-t border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-indigo-600" />
                <span>Recommended Remediation Guides:</span>
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {completionResult.remediation_guides.map((guide) => (
                  <Link
                    key={guide.id}
                    to={`/literacy/${guide.slug}`}
                    className="p-4 rounded-xl border border-slate-200 hover:border-slate-300 bg-slate-50 hover:bg-white transition-all space-y-1 block shadow-sm"
                  >
                    <span className="text-[10px] uppercase font-bold text-indigo-600">
                      Targeted Defense Guide
                    </span>
                    <h4 className="text-xs font-bold text-slate-900 line-clamp-1">{guide.title}</h4>
                    <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                      {guide.summary}
                    </p>
                  </Link>
                ))}
              </div>
            </div>
          )}

          <div className="pt-4 flex justify-center">
            <Button
              variant="outline"
              onClick={handleStartGame}
              leftIcon={<RotateCcw className="w-4 h-4" />}
            >
              Play Another Simulation Round
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
