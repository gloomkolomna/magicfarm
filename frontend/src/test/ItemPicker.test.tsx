import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ItemPicker from '../components/ItemPicker';

vi.mock('../api/media', () => ({
  mediaUrl: (url: string | null) => url || '',
}));

const many = Array.from({ length: 14 }, (_, i) => ({ key: `k${i}`, title: `Предмет ${i}` }));

describe('ItemPicker', () => {
  it('показывает первые 4 карточки (сетка 2×2) без стрелок, если предметов не больше 4', () => {
    const items = many.slice(0, 4);
    render(<ItemPicker items={items} value={null} onChange={() => {}} />);
    items.forEach((it) => expect(screen.getByText(it.title)).toBeTruthy());
    expect(screen.queryByText('◀')).toBeNull();
    expect(screen.queryByText('▶')).toBeNull();
  });

  it('показывает стрелки и счётчик, листает страницы по 4', () => {
    render(<ItemPicker items={many} value={null} onChange={() => {}} />);
    expect(screen.getByText('1 / 4')).toBeTruthy();
    expect(screen.queryByText('Предмет 4')).toBeNull();

    fireEvent.click(screen.getByText('▶'));
    expect(screen.getByText('Предмет 4')).toBeTruthy();
    expect(screen.queryByText('Предмет 0')).toBeNull();
    expect(screen.getByText('2 / 4')).toBeTruthy();

    fireEvent.click(screen.getByText('◀'));
    expect(screen.getByText('Предмет 0')).toBeTruthy();
    expect(screen.getByText('1 / 4')).toBeTruthy();
  });

  it('блокирует стрелки на краях', () => {
    render(<ItemPicker items={many} value={null} onChange={() => {}} />);
    const prev = screen.getByText('◀').closest('button') as HTMLButtonElement;
    expect(prev.disabled).toBe(true);
    fireEvent.click(screen.getByText('▶'));
    fireEvent.click(screen.getByText('▶'));
    fireEvent.click(screen.getByText('▶'));
    const next = screen.getByText('▶').closest('button') as HTMLButtonElement;
    expect(next.disabled).toBe(true);
  });

  it('клик по карточке вызывает onChange с key', () => {
    const onChange = vi.fn();
    render(<ItemPicker items={many.slice(0, 3)} value={null} onChange={onChange} />);
    fireEvent.click(screen.getByText('Предмет 1'));
    expect(onChange).toHaveBeenCalledWith('k1');
  });

  it('выделенная карточка обведена рамкой акцента', () => {
    render(<ItemPicker items={many.slice(0, 3)} value="k1" onChange={() => {}} />);
    const btn = screen.getByText('Предмет 1').closest('button') as HTMLButtonElement;
    expect(btn.style.border).toContain('var(--accent-warm)');
  });

  it('выводит изображение, если задано, иначе эмодзи', () => {
    const { rerender } = render(
      <ItemPicker items={[{ key: 'a', title: 'С img', image: '/img.png' }]} value={null} onChange={() => {}} />,
    );
    expect(screen.getByText('С img').closest('button')!.querySelector('img')).not.toBeNull();

    rerender(
      <ItemPicker items={[{ key: 'a', title: 'С эмодзи', emoji: '🌸' }]} value={null} onChange={() => {}} />,
    );
    expect(screen.getByText('С эмодзи').closest('button')!.querySelector('img')).toBeNull();
    expect(screen.getByText('🌸')).toBeTruthy();
  });

  it('подставляет дефолтный эмодзи, если нет ни картинки, ни эмодзи', () => {
    render(<ItemPicker items={[{ key: 'a', title: 'Пустышка' }]} value={null} onChange={() => {}} />);
    expect(screen.getByText('📦')).toBeTruthy();
  });

  it('показывает бейдж количества', () => {
    render(<ItemPicker items={[{ key: 'a', title: 'Товар', badge: '×3' }]} value={null} onChange={() => {}} />);
    expect(screen.getByText('×3')).toBeTruthy();
  });

  it('автоматически переходит на страницу выбранного элемента', () => {
    render(<ItemPicker items={many} value="k8" onChange={() => {}} />);
    expect(screen.getByText('Предмет 8')).toBeTruthy();
    expect(screen.getByText('3 / 4')).toBeTruthy();
  });

  it('переносит длинные названия и бейджи, не вылезая за карточку', () => {
    render(
      <ItemPicker
        items={[{ key: 'a', title: 'Оченьдлинноеназваниетоварабезпробелов', badge: 'есть 999999' }]}
        value={null}
        onChange={() => {}}
      />,
    );
    const title = screen.getByText('Оченьдлинноеназваниетоварабезпробелов');
    expect(title.style.overflowWrap).toBe('anywhere');
    expect(title.style.wordBreak).toBe('break-word');
  });

  it('не рендерит ничего при пустом списке', () => {
    const { container } = render(<ItemPicker items={[]} value={null} onChange={() => {}} />);
    expect(container.querySelector('button')).toBeNull();
  });

  it('блокирует недоступный элемент', () => {
    const onChange = vi.fn();
    render(<ItemPicker items={[{ key: 'a', title: 'Закрыто', disabled: true }]} value={null} onChange={onChange} />);
    const btn = screen.getByText('Закрыто').closest('button') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    fireEvent.click(btn);
    expect(onChange).not.toHaveBeenCalled();
  });
});
