export function extractDateFromLimitlessId(id: string): string | null {
  const match = id.match(/limitless-(\d{4}-\d{2}-\d{2})/);
  if (match) return match[1];
  if (id.includes('current')) return new Date().toISOString().split('T')[0];
  return null;
}