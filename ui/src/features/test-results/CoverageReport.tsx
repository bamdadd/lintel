import { useState, useEffect } from 'react';

interface CoverageData {
  run_id: string;
  project_id: string;
  line_rate: number;
  branch_rate: number;
  lines_covered: number;
  lines_total: number;
  branches_covered: number;
  branches_total: number;
  files: Array<{
    path: string;
    lines_covered: number;
    lines_total: number;
    branches_covered: number;
    branches_total: number;
  }>;
}

interface CoverageReportProps {
  runId: string;
}

export function CoverageReport({ runId }: CoverageReportProps) {
  const [coverage, setCoverage] = useState<CoverageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchCoverage() {
      try {
        const response = await fetch(`/api/v1/artifacts/coverage/${runId}`);
        if (response.status === 404) {
          setCoverage(null);
          return;
        }
        if (!response.ok) throw new Error('Failed to fetch coverage');
        setCoverage(await response.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchCoverage();
  }, [runId]);

  if (loading) return <div className="animate-pulse p-4">Loading coverage...</div>;
  if (error) return <div className="text-red-500 p-4">Error: {error}</div>;
  if (!coverage) return <div className="text-gray-500 p-4">No coverage data available</div>;

  const linePercent = (coverage.line_rate * 100).toFixed(1);
  const branchPercent = (coverage.branch_rate * 100).toFixed(1);

  return (
    <div className="border rounded-lg p-4 bg-white dark:bg-gray-800">
      <h3 className="text-lg font-semibold mb-3">Coverage Report</h3>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <CoverageGauge label="Line Coverage" percent={Number(linePercent)} />
        <CoverageGauge label="Branch Coverage" percent={Number(branchPercent)} />
      </div>

      <div className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        Lines: {coverage.lines_covered}/{coverage.lines_total} |
        Branches: {coverage.branches_covered}/{coverage.branches_total}
      </div>

      {coverage.files && coverage.files.length > 0 && (
        <div>
          <h4 className="text-sm font-medium mb-2">Per-file breakdown</h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 dark:text-gray-400 border-b dark:border-gray-700">
                <th className="py-1">File</th>
                <th className="py-1 text-right">Lines</th>
                <th className="py-1 text-right">Coverage</th>
              </tr>
            </thead>
            <tbody>
              {coverage.files.map((file) => {
                const rate = file.lines_total > 0
                  ? ((file.lines_covered / file.lines_total) * 100).toFixed(1)
                  : '0.0';
                return (
                  <tr key={file.path} className="border-b dark:border-gray-700">
                    <td className="py-1 font-mono text-xs">{file.path}</td>
                    <td className="py-1 text-right">{file.lines_covered}/{file.lines_total}</td>
                    <td className="py-1 text-right">
                      <span className={Number(rate) >= 80 ? 'text-green-600' : Number(rate) >= 50 ? 'text-yellow-600' : 'text-red-600'}>
                        {rate}%
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CoverageGauge({ label, percent }: { label: string; percent: number }) {
  const color = percent >= 80 ? 'text-green-600' : percent >= 50 ? 'text-yellow-600' : 'text-red-600';

  return (
    <div className="text-center">
      <div className={`text-3xl font-bold ${color}`}>{percent}%</div>
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className="mt-1 w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all ${
            percent >= 80 ? 'bg-green-500' : percent >= 50 ? 'bg-yellow-500' : 'bg-red-500'
          }`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    </div>
  );
}
