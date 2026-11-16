export function parseVkLaunchParams(search: string, hash: string) {
  const params: Record<string, string> = {};

  for (const source of [search, hash]) {
    const query = source.startsWith('?') || source.startsWith('#') ? source.slice(1) : source;
    if (!query) continue;
    new URLSearchParams(query).forEach((value, key) => {
      if (key === 'sign' || key.startsWith('vk_')) params[key] = value;
    });
  }

  const id = Number(params.vk_user_id);
  return {
    vkUserId: params.vk_user_id && Number.isInteger(id) && id > 0 ? id : null,
    params,
  };
}
