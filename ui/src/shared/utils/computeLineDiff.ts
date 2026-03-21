/**
 * Simple line-level diff between two strings.
 * Produces a list of lines tagged as 'equal', 'added', or 'removed'.
 * Uses a basic LCS (longest common subsequence) approach on lines.
 */

export interface DiffEntry {
  type: 'equal' | 'added' | 'removed';
  text: string;
}

export function computeLineDiff(original: string, edited: string): DiffEntry[] {
  const oldLines = original.split('\n');
  const newLines = edited.split('\n');

  const m = oldLines.length;
  const n = newLines.length;

  // Build LCS table for backtracking
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  let i = m;
  let j = n;

  // Backtrack from bottom-right, collecting entries in reverse
  const entries: DiffEntry[] = [];
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      entries.push({ type: 'equal', text: oldLines[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      entries.push({ type: 'added', text: newLines[j - 1] });
      j--;
    } else {
      entries.push({ type: 'removed', text: oldLines[i - 1] });
      i--;
    }
  }

  return entries.reverse();
}
