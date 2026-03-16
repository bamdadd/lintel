import { useState, useEffect, useCallback } from 'react';

interface QualityGateRule {
  rule_id: string;
  project_id: string;
  rule_type: string;
  threshold: number;
  severity: string;
  enabled: boolean;
}

interface QualityGateRulesEditorProps {
  projectId: string;
}

const RULE_TYPES = [
  { value: 'min_pass_rate', label: 'Minimum Pass Rate (%)', defaultThreshold: 80 },
  { value: 'min_coverage', label: 'Minimum Coverage (%)', defaultThreshold: 70 },
  { value: 'max_coverage_drop', label: 'Max Coverage Drop (pp)', defaultThreshold: 2 },
];

export function QualityGateRulesEditor({ projectId }: QualityGateRulesEditorProps) {
  const [rules, setRules] = useState<QualityGateRule[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchRules = useCallback(async () => {
    try {
      const response = await fetch(`/api/v1/projects/${projectId}/quality-gate-rules`);
      if (response.ok) setRules(await response.json());
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { fetchRules(); }, [fetchRules]);

  const addRule = async (ruleType: string, threshold: number) => {
    const response = await fetch(`/api/v1/projects/${projectId}/quality-gate-rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rule_type: ruleType, threshold, severity: 'error', enabled: true }),
    });
    if (response.ok) await fetchRules();
  };

  const deleteRule = async (ruleId: string) => {
    const response = await fetch(`/api/v1/projects/${projectId}/quality-gate-rules/${ruleId}`, {
      method: 'DELETE',
    });
    if (response.ok) setRules(rules.filter(r => r.rule_id !== ruleId));
  };

  if (loading) return <div className="animate-pulse p-4">Loading rules...</div>;

  return (
    <div className="border rounded-lg p-4 bg-white dark:bg-gray-800">
      <h3 className="text-lg font-semibold mb-3">Quality Gate Rules</h3>

      {rules.length > 0 && (
        <table className="w-full text-sm mb-4">
          <thead>
            <tr className="text-left text-gray-500 dark:text-gray-400 border-b dark:border-gray-700">
              <th className="py-2">Rule Type</th>
              <th className="py-2 text-right">Threshold</th>
              <th className="py-2 text-center">Severity</th>
              <th className="py-2 text-center">Enabled</th>
              <th className="py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.rule_id} className="border-b dark:border-gray-700">
                <td className="py-2">
                  {RULE_TYPES.find(t => t.value === rule.rule_type)?.label || rule.rule_type}
                </td>
                <td className="py-2 text-right font-mono">{rule.threshold}</td>
                <td className="py-2 text-center">
                  <span className={`px-2 py-0.5 text-xs rounded ${
                    rule.severity === 'error'
                      ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200'
                      : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-200'
                  }`}>
                    {rule.severity}
                  </span>
                </td>
                <td className="py-2 text-center">{rule.enabled ? '\u2713' : '\u2717'}</td>
                <td className="py-2 text-right">
                  <button
                    onClick={() => deleteRule(rule.rule_id)}
                    className="text-red-600 hover:text-red-800 text-xs"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="flex gap-2 items-end">
        <select id="ruleType" className="border rounded px-2 py-1 text-sm dark:bg-gray-700 dark:border-gray-600">
          {RULE_TYPES.map(t => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <input
          id="threshold"
          type="number"
          placeholder="Threshold"
          className="border rounded px-2 py-1 text-sm w-24 dark:bg-gray-700 dark:border-gray-600"
          defaultValue="80"
        />
        <button
          onClick={() => {
            const typeEl = document.getElementById('ruleType') as HTMLSelectElement;
            const thresholdEl = document.getElementById('threshold') as HTMLInputElement;
            addRule(typeEl.value, Number(thresholdEl.value));
          }}
          className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
        >
          Add Rule
        </button>
      </div>
    </div>
  );
}
