/**
 * TypeScript Schema Definitions for ScamShield Backend APIs
 * Synced with OpenAPI 3.0 specification & Django Data Models
 */

// ==========================================
// 1. Common & Infrastructure
// ==========================================

export interface ApiErrorDetail {
  [key: string]: string[] | string | Record<string, string[]>;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: ApiErrorDetail;
    request_id?: string;
  };
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ==========================================
// 2. Authentication & Accounts
// ==========================================

export type UserRole = 'CITIZEN' | 'ANALYST' | 'EDUCATOR' | 'ADMIN';
export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  approval_status: ApprovalStatus;
  organization?: string | null;
  credential_note?: string | null;
  created_at: string;
}

export interface LoginResponse {
  access: string;
  user: User;
}

export interface RefreshResponse {
  access: string;
  user: User;
}

// ==========================================
// 3. Scam Reports & Indicators
// ==========================================

export type ScamCategory =
  | 'PHISHING'
  | 'INVESTMENT'
  | 'E_COMMERCE'
  | 'JOB'
  | 'LOAN'
  | 'IMPERSONATION'
  | 'LOVE_ROMANCE'
  | 'OTHER';

export type PlatformType =
  | 'WHATSAPP'
  | 'TELEGRAM'
  | 'SMS'
  | 'FACEBOOK'
  | 'INSTAGRAM'
  | 'TIKTOK'
  | 'EMAIL'
  | 'PHONE_CALL'
  | 'WEBSITE'
  | 'OTHER';

export type PaymentMethod =
  | 'BANK_TRANSFER'
  | 'CREDIT_DEBIT_CARD'
  | 'E_WALLET'
  | 'CRYPTOCURRENCY'
  | 'GIFT_CARD'
  | 'CASH'
  | 'NONE';

export type ReportStatus = 'PENDING' | 'VERIFIED' | 'REJECTED';

export type IndicatorType = 'PHONE' | 'URL' | 'DOMAIN' | 'EMAIL' | 'BANK_ACCOUNT';

export interface ReportIndicator {
  id?: string;
  indicator_type: IndicatorType;
  raw_value: string;
  normalized_value?: string;
  display_value?: string;
}

export interface RecoveryStep {
  title: string;
  detail: string;
}

export interface RecoveryPlaybook {
  title: string;
  steps: RecoveryStep[];
  hotlines: Array<{
    name: string;
    number: string;
    hours?: string;
  }>;
}

export interface ScamReport {
  id: string;
  reference_code: string;
  status: ReportStatus;
  category: ScamCategory;
  platform: PlatformType;
  message_text: string;
  financial_loss: string;
  currency: string;
  payment_method: PaymentMethod;
  created_at: string;
  indicators?: ReportIndicator[];
  is_anonymous: boolean;
  playbook?: RecoveryPlaybook;
}

export interface CreateReportResponse {
  reference_code: string;
  status: ReportStatus;
  access_key?: string; // Anonymous submissions only
  playbook: RecoveryPlaybook;
}

export interface TrackReportResponse {
  reference_code: string;
  status: ReportStatus;
  category: ScamCategory;
  created_at: string;
  playbook: RecoveryPlaybook;
}

// ==========================================
// 4. Intelligence & Lookups
// ==========================================

export interface VerifiedIndicator {
  id: string;
  indicator_type: IndicatorType;
  normalized_value: string;
  display_value: string;
  threat_level: 'HIGH' | 'MEDIUM' | 'LOW';
  confidence_score: number;
  report_count: number;
  public_note: string;
  is_active: boolean;
  first_confirmed_at: string;
  last_confirmed_at: string;
}

export interface AuditLogItem {
  id: string;
  event_type: string;
  severity: string;
  actor_id: string | null;
  actor_email?: string | null;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export type VerdictLevel = 'RED' | 'YELLOW' | 'GREEN' | 'UNKNOWN';

export interface LookupMatch {
  indicator_type: IndicatorType;
  display_value: string;
  threat_level?: string;
  first_seen?: string;
  last_confirmed?: string;
  report_count?: number;
  public_note?: string;
}

export interface LookupResponse {
  input: string;
  detected_type: IndicatorType | null;
  verdict: VerdictLevel;
  verdict_title: string;
  verdict_description: string;
  matches: LookupMatch[];
  query_id?: string;
}

// ==========================================
// 5. Threat Broadcasts & Advisories
// ==========================================

export type AudienceGroup = 'GENERAL' | 'ELDERLY' | 'TEENAGER' | 'NON_TECH' | 'ALL';
export type AdvisoryStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';

export interface ThreatAdvisory {
  id: string;
  title: string;
  summary: string;
  content: string;
  audience_group: AudienceGroup;
  status: AdvisoryStatus;
  primary_category: ScamCategory;
  published_at?: string | null;
  created_at: string;
  updated_at: string;
}

// ==========================================
// 6. Literacy Hub & CMS
// ==========================================

export type GuideStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';

export interface GuideAsset {
  id: string;
  asset_type: 'IMAGE' | 'AUDIO' | 'DOCUMENT';
  url: string;
  alt_text: string;
  file_size_bytes: number;
}

export interface LiteracyGuide {
  id: string;
  slug: string;
  title: string;
  summary: string;
  body_markdown: string;
  status: GuideStatus;
  audience_groups: AudienceGroup[];
  tactics: string[];
  reading_time_minutes: number;
  assets?: GuideAsset[];
  published_at?: string | null;
  created_at: string;
}

// ==========================================
// 7. Spot the Scam Simulator
// ==========================================

export type ScenarioTactic =
  | 'URGENCY'
  | 'AUTHORITY'
  | 'FEAR'
  | 'GREED'
  | 'FAMILIARITY'
  | 'ISOLATION'
  | 'NONE';

export interface ScenarioRedFlag {
  id?: string;
  flag_code?: string;
  x_pct: number | string;
  y_pct: number | string;
  w_pct?: number | string;
  h_pct?: number | string;
  explanation: string;
}

export interface SimulatorScenario {
  id: string;
  title: string;
  channel?: string;
  context_prompt?: string;
  image_url: string;
  image_alt?: string;
  difficulty?: number;
  // Masked during active attempt
  is_scam?: boolean;
  tactic?: ScenarioTactic;
  explanation?: string;
  red_flags?: ScenarioRedFlag[];
}

export interface SimulatorAttemptInitResponse {
  attempt_id: string;
  session_key?: string;
  scenario_count: number;
  scenarios: SimulatorScenario[];
}

export interface AnswerFeedbackResponse {
  scenario_id: string;
  is_correct: boolean;
  explanation: string;
  red_flags: ScenarioRedFlag[];
}

export interface SimulatorAttemptCompletionResponse {
  attempt_id: string;
  status: string;
  score_pct: number;
  completed_at: string;
  profile: {
    total_scenarios: number;
    correct_scenarios: number;
    blind_spots: string[];
    missed_tactics?: Record<string, number>;
  };
  remediation_guides: LiteracyGuide[];
}

export interface StudioScenario {
  id: string;
  title: string;
  channel: string;
  is_scam: boolean;
  tactic: ScenarioTactic;
  difficulty: number;
  image_url: string;
  image_alt: string;
  explanation: string;
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';
  red_flags: ScenarioRedFlag[];
  created_at: string;
}
