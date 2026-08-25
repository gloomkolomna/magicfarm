import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import RulesPage from '../pages/Rules';

const GUIDE_MD = '# Правила игры\n\n> Это описание игры.\n\n---\n\n## Оглавление\n\n1. [Первый](#1-первый)\n\n## 1. Первый\n\nТекст **правил** и `код`.\n\n| А | Б |\n|---|---|\n| 1 | 2 |\n';

function mockFetch(md: string | null) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: md != null,
    status: md != null ? 200 : 404,
    text: () => Promise.resolve(md ?? ''),
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('RulesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders title and fetched markdown content', async () => {
    mockFetch(GUIDE_MD);
    render(<RulesPage />);

    expect(screen.getByText('Загрузка правил…')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('📜 Правила игры')).toBeInTheDocument();
    });

    expect(screen.getByText('Первый')).toBeInTheDocument();
    expect(screen.getByText(/правил/)).toBeInTheDocument();
    expect(document.querySelector('table')).toBeInTheDocument();
  });

  it('keeps manual toc and does not add auto toc', async () => {
    mockFetch(GUIDE_MD);
    render(<RulesPage />);

    await waitFor(() => {
      expect(screen.getByText('📜 Правила игры')).toBeInTheDocument();
    });

    expect(screen.getByText('Оглавление')).toBeInTheDocument();
    expect(document.querySelector('.fm-rules .toc')).not.toBeInTheDocument();
  });

  it('shows error message when fetch fails', async () => {
    mockFetch(null);
    render(<RulesPage />);

    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить правила/)).toBeInTheDocument();
    });
  });
});
