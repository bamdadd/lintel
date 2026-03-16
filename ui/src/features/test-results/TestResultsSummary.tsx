import { useState, useEffect } from 'react';

interface TestResult {
  run_id: string;
  project_id: string;
  artifact_id: string;
  total: number;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  pass_rate: number;
  duration_ms: number;
  quality_gate_status: string;
}

interface TestResultsSummaryProps {
  runId: string;
}

export function TestResultsSummary({ runId }: TestResultsSummaryProps) {
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchResults() {
      try {
        const response = await fetch(`/api/v1/artifacts/test-results/${runId}`);
        if (!response.ok) throw new Error('Failed to fetch test results');
        const data = await response.json();
        setResults(Array.isArray(data) ? data : [data]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchResults();
  }, [runId]);

  if (loading) return <div className="animate-pulse p-4">Loading test results...</div>;
  if (error) return <div className="text-red-500 p-4">Error: {error}</div>;
  if (results.length === 0) return <div className="text-gray-500 p-4">No test results available</div>;

  return (
    <div className="space-y-4">
      {results.map((result, idx) => (
        <div key={idx} className="border rounded-lg p-4 bg-white dark:bg-gray-800">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold">Test Results</h3>
            <QualityGateBadge status={result.quality_gate_status} />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatCard label="Total" value={result.total} color="text-gray-700 dark:text-gray-300" />
            <StatCard label="Passed" value={result.passed} color="text-green-600" />
            <StatCard label="Failed" value={result.failed} color="text-red-600" />
            <StatCard label="Errors" value={result.errors} color="text-orange-600" />
            <StatCard label="Skipped" value={result.skipped} color="text-yellow-600" />
          </div>

          <div className="mt-3 flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
            <span>Pass rate: <strong>{result.pass_rate.toFixed(1)}%</strong></span>
            <span>Duration: <strong>{(result.duration_ms / 1000).toFixed(2)}s</strong></span>
          </div>

          {result.total > 0 && (
            <div className="mt-3 w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div
                className="bg-green-500 h-2 rounded-full transition-all"
                style={{ width: `${result.pass_rate}%` }}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="text-center">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
    </div>
  );
}

function QualityGateBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    passed: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  };

  const style = styles[status] || styles.pending;

  return (
    <span className={`px-2 py-1 text-xs font-medium rounded-full ${style}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
