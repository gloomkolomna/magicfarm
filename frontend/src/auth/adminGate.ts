const ADMIN_VK_IDS: Set<number> = new Set([400977, 795384]);

export function isAdminAllowed(vkUserId: number | null): boolean {
  if (vkUserId == null) return false;
  return ADMIN_VK_IDS.has(vkUserId);
}
