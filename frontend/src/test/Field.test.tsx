import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import FieldPage from '../pages/Field';

vi.mock('../context/SessionContext', () => ({
  useSession: () => ({ refresh: vi.fn(), loading: false }),
}));

vi.mock('../api/endpoints', () => {
  const mockField = {
    id: 1, code: 'field1', name: 'Грядки',
    map_url: '/farm/map.png', cols: 3, rows: 2, grid_color: '#333',
    plant_category: null, min_level: 0, field_kind: null,
    created_at: null,
    cells: [
      { id: 1, col: 0, row: 0, kind: 'bed', plant_id: null, occupant_user_id: null, tent_id: null, plant_name: null, plant_emoji: null, plant_image_young: null, plant_image_grown: null, plot: null, tent_name: null, tent_image: null, occupant_name: null },
      { id: 2, col: 1, row: 0, kind: 'bed', plant_id: null, occupant_user_id: null, tent_id: null, plant_name: null, plant_emoji: null, plant_image_young: null, plant_image_grown: null, plot: null, tent_name: null, tent_image: null, occupant_name: null },
      { id: 3, col: 2, row: 0, kind: 'bed', plant_id: null, occupant_user_id: null, tent_id: null, plant_name: null, plant_emoji: null, plant_image_young: null, plant_image_grown: null, plot: null, tent_name: null, tent_image: null, occupant_name: null },
      { id: 4, col: 0, row: 1, kind: 'bed', plant_id: 1, occupant_user_id: 123, tent_id: null, plant_name: 'Хлебозлак', plant_emoji: '🌾', plant_image_young: null, plant_image_grown: null,
        plot: { id: 10, plant_id: 1, plant_name: 'Хлебозлак', plant_emoji: '🌾', qty: 3, status: 'planted', accumulated: 0, required: 900, crystal_color: 'violet', crystal_count: 3, drawn_cards_json: '[{"color":"violet","value":3,"is_treasure":false}]', norm_revealed: false, created_at: null, completed_at: null },
        tent_name: null, tent_image: null, occupant_name: null },
    ],
    plants: [{ id: 1, code: 'khlebozlak', name: 'Хлебозлак', emoji: '🌾', category: 'garden', level: 1, norm_per_crystal: 100, description: null, image_url: null, image_young_url: null, image_grown_url: null }],
    tents: [],
  };

  return {
    api: {
      fieldDetail: vi.fn().mockResolvedValue(mockField),
      products: vi.fn().mockResolvedValue([]),
      plantOnCell: vi.fn().mockResolvedValue({}),
      investPlot: vi.fn().mockResolvedValue({}),
      harvestCell: vi.fn().mockResolvedValue({}),
      createStitchReport: vi.fn().mockResolvedValue({}),
      revealNorm: vi.fn().mockResolvedValue({ id: 10, norm_revealed: true }),
      gameMediaByCode: vi.fn().mockRejectedValue(new Error('not found')),
      crystalCards: vi.fn().mockResolvedValue([]),
      plants: vi.fn().mockResolvedValue([]),
      animalsAvailable: vi.fn().mockResolvedValue([]),
      petsCatalog: vi.fn().mockResolvedValue([]),
    },
  };
});

vi.mock('../api/media', () => ({
  mediaUrl: (url: string | null) => url || '',
  compressImage: vi.fn((f: File) => Promise.resolve(f)),
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter initialEntries={['/field/1']}>
    <Routes>
      <Route path="/field/:id" element={children} />
    </Routes>
  </MemoryRouter>
);

describe('FieldPage — care modal states', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders field cells', async () => {
    render(<Wrapper><FieldPage /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('🗺️ Грядки')).toBeInTheDocument();
    });
  });

  it('shows "Узнать норму" button for unrevealed planted plot', async () => {
    render(<Wrapper><FieldPage /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('🗺️ Грядки')).toBeInTheDocument();
    });
    const cells = document.querySelectorAll('[style*="cursor: pointer"]');
    expect(cells.length).toBeGreaterThanOrEqual(4);
    fireEvent.click(cells[3]);
    await waitFor(() => {
      expect(screen.getByText('🔮 Узнать норму')).toBeInTheDocument();
    });
  });

  it('shows stitch report form after norm is revealed', async () => {
    render(<Wrapper><FieldPage /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('🗺️ Грядки')).toBeInTheDocument();
    });
    const cells = document.querySelectorAll('[style*="cursor: pointer"]');
    fireEvent.click(cells[3]);
    await waitFor(() => {
      expect(screen.getByText('🔮 Узнать норму')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('🔮 Узнать норму'));
    await waitFor(() => {
      expect(screen.getByText('📷 Отчитаться о вышивке')).toBeInTheDocument();
    });
  });

  it('does not show invest block', async () => {
    render(<Wrapper><FieldPage /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('🗺️ Грядки')).toBeInTheDocument();
    });
    const cells = document.querySelectorAll('[style*="cursor: pointer"]');
    fireEvent.click(cells[3]);
    await waitFor(() => {
      expect(screen.getByText('🔮 Узнать норму')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('🔮 Узнать норму'));
    await waitFor(() => {
      expect(screen.getByText('📷 Отчитаться о вышивке')).toBeInTheDocument();
    });
    expect(screen.queryByText('Полить крестиками')).not.toBeInTheDocument();
    expect(screen.queryByText('Вложить крестиков')).not.toBeInTheDocument();
  });
});

describe('FieldPage — zoom controls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders zoom controls and changes scale', async () => {
    render(<Wrapper><FieldPage /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('🗺️ Грядки')).toBeInTheDocument();
    });
    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(screen.getByLabelText('Вместить в экран')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Увеличить'));
    expect(screen.getByText('125%')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Уменьшить'));
    expect(screen.getByText('100%')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Увеличить'));
    fireEvent.click(screen.getByLabelText('Увеличить'));
    expect(screen.getByText('156%')).toBeInTheDocument();

    fireEvent.click(screen.getByText('156%'));
    expect(screen.getByText('100%')).toBeInTheDocument();
  });
});
