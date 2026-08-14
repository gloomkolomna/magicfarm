import { describe, it, expect, beforeEach, vi } from 'vitest';

const { postMock, compressMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  compressMock: vi.fn(),
}));

vi.mock('../api/client', () => ({ default: { post: postMock } }));
vi.mock('../api/media', () => ({ compressImage: compressMock }));

import { api } from '../api/endpoints';

describe('api.createStitchReport — client-side compression', () => {
  beforeEach(() => {
    postMock.mockReset();
    compressMock.mockReset();
  });

  it('compresses both photos, appends results, and lets the browser set Content-Type', async () => {
    const before = new File(['b'], 'before.heic', { type: 'image/heic' });
    const after = new File(['a'], 'after.jpg', { type: 'image/jpeg' });
    const beforeC = new File(['bc'], 'before.jpg', { type: 'image/jpeg' });
    const afterC = new File(['ac'], 'after.jpg', { type: 'image/jpeg' });
    compressMock.mockImplementation((f: File) =>
      Promise.resolve(f === before ? beforeC : afterC),
    );
    postMock.mockResolvedValue({ data: { id: 1 } });

    await api.createStitchReport(150, before, after, 'заметка', 'plant_grow', 7, 3);

    expect(compressMock).toHaveBeenCalledTimes(2);
    expect(postMock).toHaveBeenCalledTimes(1);
    expect(postMock.mock.calls[0][0]).toBe('/stitches/reports');

    const form = postMock.mock.calls[0][1];
    expect(form.get('amount')).toBe('150');
    expect(form.get('note')).toBe('заметка');
    expect(form.get('context_type')).toBe('plant_grow');
    expect(form.get('context_id')).toBe('7');
    expect(form.get('cell_id')).toBe('3');
    expect(form.get('photo_before')).toBe(beforeC);
    expect(form.get('photo_after')).toBe(afterC);

    const opts = postMock.mock.calls[0][2];
    expect(opts?.headers?.['Content-Type']).toBe('multipart/form-data');
  });

  it('falls back to the original file when compression fails', async () => {
    const before = new File(['b'], 'before.jpg', { type: 'image/jpeg' });
    const after = new File(['a'], 'after.jpg', { type: 'image/jpeg' });
    compressMock.mockRejectedValue(new Error('canvas unavailable'));
    postMock.mockResolvedValue({ data: { id: 2 } });

    await api.createStitchReport(10, before, after);

    const form = postMock.mock.calls[0][1];
    expect(form.get('photo_before')).toBe(before);
    expect(form.get('photo_after')).toBe(after);
  });
});
