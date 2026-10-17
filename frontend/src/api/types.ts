// Mirrors backend/app/schemas.py. Keep the two in sync when the API changes.

export type AssessmentStatus = 'active' | 'completed' | 'expired';
export type StopReason = 'precision_reached' | 'max_questions' | 'item_bank_exhausted';

export interface TopicInfo {
  name: string;
  description: string;
  question_count: number;
}

export interface ServedQuestion {
  question_id: string;
  position: number;
  topic: string;
  stem: string;
  options: string[];
}

export interface AssessmentState {
  assessment_id: string;
  status: AssessmentStatus;
  topics: string[];
  progress: { answered: number; max_questions: number; min_questions: number };
  current_question: ServedQuestion | null;
  stop_reason: StopReason | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  expires_at: string | null;
}

export interface AnswerFeedback {
  question_id: string;
  correct: boolean;
  selected_index: number;
  correct_index: number;
  explanation: string;
}

export interface AnswerResponse {
  feedback: AnswerFeedback;
  assessment: AssessmentState;
}

export interface AbilitySummary {
  theta: number;
  se: number;
  ci95_low: number;
  ci95_high: number;
  band: string;
  band_description: string;
}

export interface TopicResult {
  topic: string;
  answered: number;
  correct: number;
  accuracy: number;
  theta: number;
  se: number;
  sufficient_data: boolean;
}

export interface TrajectoryPoint {
  position: number;
  theta: number;
  se: number;
}

export interface ReviewItem {
  position: number;
  question_id: string;
  topic: string;
  stem: string;
  options: string[];
  selected_index: number;
  correct_index: number;
  correct: boolean;
  explanation: string;
  tags: string[];
  time_seconds: number | null;
}

export interface StudyPlanStep {
  title: string;
  topic: string;
  rationale: string;
  actions: string[];
  evidence_positions: number[];
}

export interface StudyPlan {
  source: 'ai' | 'rule_based';
  generated_at: string;
  summary: string;
  steps: StudyPlanStep[];
  notice: string | null;
  model: string | null;
}

export interface Results {
  assessment_id: string;
  status: AssessmentStatus;
  topics: string[];
  stop_reason: StopReason | null;
  created_at: string;
  completed_at: string | null;
  ability: AbilitySummary;
  answered: number;
  correct: number;
  accuracy: number;
  topic_results: TopicResult[];
  trajectory: TrajectoryPoint[];
  review: ReviewItem[];
  study_plan: StudyPlan | null;
  model_notice: string;
}

export interface Health {
  status: 'ok' | 'degraded';
  version: string;
  database: { status: 'up' | 'down' };
  ai: { status: 'configured' | 'not_configured' };
}
