/**
 * API client functions for review reports and scores (REQ-006).
 */

const API_BASE = '/api/v1';

export interface ReviewReport {
  report_id: string;
  pipeline_run_id: string;
  repo_id: string;
  contributor_id: string;
  commit_shas: string[];
  per_file_scores: PerFileScore[];
  aggregate_scores: Record<string, number>;
  storage_backend: string;
}

export interface PerFileScore {
  file_path: string;
  dimension: string;
  score: number;
  severity: string;
  findings: ReviewFinding[];
}

export interface ReviewFinding {
  message: string;
  severity: string;
  line_start: number | null;
  line_end: number | null;
  rule_id: string;
  suggestion: string;
}

export interface ReviewScoreRecord {
  score_id: string;
  repo_id: string;
  contributor_id: string;
  pipeline_run_id: string;
  dimension: string;
  score: number;
  severity: string;
  recorded_at: string;
}

export async function fetchReviewReports(repoId: string): Promise<ReviewReport[]> {
  const res = await fetch(`${API_BASE}/repositories/${repoId}/review-reports`);
  if (!res.ok) throw new Error(`Failed to fetch review reports: ${res.status}`);
  return res.json();
}

export async function fetchReviewReport(reportId: string): Promise<ReviewReport> {
  const res = await fetch(`${API_BASE}/review-reports/${reportId}`);
  if (!res.ok) throw new Error(`Failed to fetch review report: ${res.status}`);
  return res.json();
}

export async function fetchScoreTrends(
  repoId: string,
  dimension?: string,
): Promise<ReviewScoreRecord[]> {
  const params = new URLSearchParams();
  if (dimension) params.set('dimension', dimension);
  const qs = params.toString();
  const url = `${API_BASE}/repositories/${repoId}/review-scores/trends${qs ? `?${qs}` : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch score trends: ${res.status}`);
  return res.json();
}
