import { describe, it, expect, beforeEach } from 'vitest';
import { AxiosError } from 'axios';
import client, { setVkLaunchInfo } from '../api/client';

function withAdapter(handler: (config: any) => any) {
  (client.defaults as any).adapter = async (config: any) => {
    const res = handler(config);
    const validate = config.validateStatus || ((s: number) => s >= 200 && s < 300);
    if (!validate(res.status)) {
      throw new AxiosError(
        `Request failed with status code ${res.status}`,
        AxiosError.ERR_BAD_REQUEST,
        config,
        null,
        res,
      );
    }
    return res;
  };
}

describe('axios client — 401 auto-relogin', () => {
  beforeEach(() => {
    localStorage.clear();
    setVkLaunchInfo(null, {});
  });

  it('re-logs in and retries the failed request with a fresh token', async () => {
    setVkLaunchInfo(123, { sign: 'sig' });
    let meCalls = 0;
    let sessionCalls = 0;
    const meAuth: string[] = [];

    withAdapter((config) => {
      const url: string = config.url || '';
      if (url.includes('/auth/session')) {
        sessionCalls++;
        return { status: 200, data: { token: 'NEW' }, statusText: 'OK', headers: {}, config };
      }
      if (url.includes('/me')) {
        meCalls++;
        meAuth.push(config.headers?.Authorization || '');
        if (meCalls === 1) {
          return { status: 401, data: { detail: 'expired' }, statusText: 'Unauthorized', headers: {}, config };
        }
        return { status: 200, data: { vk_id: 123 }, statusText: 'OK', headers: {}, config };
      }
      return { status: 404, data: {}, statusText: 'NF', headers: {}, config };
    });

    const res = await client.get('/me');

    expect(res.status).toBe(200);
    expect(meCalls).toBe(2);
    expect(sessionCalls).toBe(1);
    expect(localStorage.getItem('token')).toBe('NEW');
    expect(meAuth[0]).toBe('');
    expect(meAuth[1]).toBe('Bearer NEW');
  });

  it('does not recurse when /auth/session itself returns 401', async () => {
    setVkLaunchInfo(123, { sign: 'sig' });
    let meCalls = 0;
    let sessionCalls = 0;

    withAdapter((config) => {
      const url: string = config.url || '';
      if (url.includes('/auth/session')) {
        sessionCalls++;
        return { status: 401, data: { detail: 'bad sign' }, statusText: 'Unauthorized', headers: {}, config };
      }
      if (url.includes('/me')) {
        meCalls++;
        return { status: 401, data: { detail: 'expired' }, statusText: 'Unauthorized', headers: {}, config };
      }
      return { status: 500, data: {}, statusText: 'ERR', headers: {}, config };
    });

    await expect(client.get('/me')).rejects.toBeDefined();
    expect(meCalls).toBe(1);
    expect(sessionCalls).toBe(1);
  });

  it('skips relogin when no vk user id is available', async () => {
    setVkLaunchInfo(null, {});
    let meCalls = 0;
    let sessionCalls = 0;

    withAdapter((config) => {
      const url: string = config.url || '';
      if (url.includes('/auth/session')) {
        sessionCalls++;
        return { status: 200, data: { token: 'X' }, statusText: 'OK', headers: {}, config };
      }
      if (url.includes('/me')) {
        meCalls++;
        return { status: 401, data: {}, statusText: 'Unauthorized', headers: {}, config };
      }
      return { status: 500, data: {}, statusText: 'ERR', headers: {}, config };
    });

    await expect(client.get('/me')).rejects.toBeDefined();
    expect(meCalls).toBe(1);
    expect(sessionCalls).toBe(0);
    expect(localStorage.getItem('token')).toBeNull();
  });
});
