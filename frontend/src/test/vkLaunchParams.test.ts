import { describe, expect, it } from 'vitest';
import { parseVkLaunchParams } from '../api/vkLaunchParams';

describe('VK launch params', () => {
  it('keeps desktop sign intact and preserves all vk params when hash is present', () => {
    const result = parseVkLaunchParams(
      '?vk_app_id=54712760&vk_user_id=168732789&vk_platform=desktop_web&vk_new_parameter=value&sign=abc_-',
      '#/profile',
    );

    expect(result).toEqual({
      vkUserId: 168732789,
      params: {
        vk_app_id: '54712760',
        vk_user_id: '168732789',
        vk_platform: 'desktop_web',
        vk_new_parameter: 'value',
        sign: 'abc_-',
      },
    });
  });

  it('reads launch params from hash without mixing them into query values', () => {
    const result = parseVkLaunchParams('', '#vk_user_id=85828300&vk_platform=desktop_web&sign=hash-sign');

    expect(result.vkUserId).toBe(85828300);
    expect(result.params.sign).toBe('hash-sign');
    expect(result.params.vk_platform).toBe('desktop_web');
  });

  it('decodes values and rejects a missing or invalid user id', () => {
    expect(parseVkLaunchParams('?vk_user_id=123&vk_ref=group%20catalog', '').params.vk_ref).toBe('group catalog');
    expect(parseVkLaunchParams('?vk_app_id=54712760&sign=abc', '').vkUserId).toBeNull();
    expect(parseVkLaunchParams('?vk_user_id=not-a-number', '').vkUserId).toBeNull();
  });
});
