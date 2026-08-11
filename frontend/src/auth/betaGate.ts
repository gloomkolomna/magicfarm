const BETA_IDS_RAW = import.meta.env.VITE_BETA_VK_IDS || '';

const BETA_IDS: Set<number> = new Set(
  BETA_IDS_RAW
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n) && n > 0),
);

export function isBetaAllowed(vkUserId: number | null): boolean {
  if (vkUserId == null) return false;
  return BETA_IDS.has(vkUserId);
}

export function hasBetaList(): boolean {
  return BETA_IDS.size > 0;
}
