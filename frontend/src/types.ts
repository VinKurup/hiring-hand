export interface ResumeListItem {
  id: number;
  filename: string;
  created_at: string;
}

export interface ResumeDetail extends ResumeListItem {
  parsed: unknown; // the JSON Resume object; rendered loosely
}

export interface Job {
  id: number;
  label: string;
  description: string;
  included: boolean;
  created_at: string;
}

export type MustHaveCategory = "tech" | "domain" | "seniority" | "qualification";

export interface MustHave {
  skill: string;
  category: MustHaveCategory;
  frequency: number;
}

export interface RoleProfile {
  title: string;
  job_count: number;
  must_haves: MustHave[];
}

export type MatchStatus = "strong" | "weak" | "missing";

export interface MustHaveMatch {
  skill: string;
  status: MatchStatus;
  evidence: string;
  claim_without_evidence: boolean;
}

export interface BuildRecommendation {
  project: string;
  stack: string[];
  closes_gap: string;
}

export interface GithubRecommendation {
  action: string;
  closes_gap: string;
}

export interface LearnRecommendation {
  skill: string;
  score_impact: "high" | "medium" | "low";
}

export interface Recommendations {
  build: BuildRecommendation[];
  github: GithubRecommendation[];
  learn: LearnRecommendation[];
}

export interface Evaluation {
  id: number;
  resume_id: number;
  visibility_score: number;
  evidence_score: number;
  role_profile: RoleProfile;
  match: { matches: MustHaveMatch[]; visibility_score: number; evidence_score: number };
  recommendations: Recommendations;
  created_at: string;
}
