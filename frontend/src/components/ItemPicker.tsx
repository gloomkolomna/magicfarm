import { useEffect, useState, type CSSProperties } from 'react';
import { mediaUrl } from '../api/media';

export interface PickerItem {
  key: string;
  title: string;
  image?: string | null;
  emoji?: string | null;
  badge?: string;
  disabled?: boolean;
}

function arrowStyle(disabled: boolean): CSSProperties {
  return {
    alignSelf: 'center', flexShrink: 0, cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.4 : 1, padding: '6px 8px', fontSize: 18,
    background: 'transparent', border: 'none', color: 'inherit', touchAction: 'manipulation',
  };
}

export default function ItemPicker({ items, value, onChange, columns = 3, pageSize = 6, compact = false, busy = false }: {
  items: PickerItem[];
  value: string | null;
  onChange: (key: string) => void;
  columns?: number;
  pageSize?: number;
  compact?: boolean;
  busy?: boolean;
}) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(items.length / pageSize));

  useEffect(() => {
    const idx = value != null ? items.findIndex((i) => i.key === value) : -1;
    if (idx >= 0) setPage(Math.floor(idx / pageSize));
    else setPage((p) => Math.min(p, pages - 1));
  }, [items, value, pageSize, pages]);

  if (items.length === 0) return null;

  const start = page * pageSize;
  const visible = items.slice(start, start + pageSize);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'stretch', gap: 6 }}>
        {pages > 1 && (
          <button type="button" disabled={page === 0 || busy} onClick={() => setPage(page - 1)} style={arrowStyle(page === 0)} aria-label="Назад">◀</button>
        )}
        <div style={{ flex: '1 1 auto', minWidth: 0, display: 'grid', gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`, gap: compact ? 4 : 8 }}>
          {visible.map((it) => {
            const selected = value === it.key;
            return (
              <button
                key={it.key}
                type="button"
                className="fm-card fm-rise"
                disabled={busy || it.disabled}
                onClick={() => onChange(it.key)}
                style={{
                  padding: compact ? 4 : 8, textAlign: 'center', cursor: 'pointer',
                  border: selected ? '2px solid var(--accent-warm)' : '1px solid var(--border)',
                  opacity: it.disabled ? 0.5 : 1,
                }}
              >
                {it.image && !compact ? (
                  <img src={mediaUrl(it.image)} alt="" style={{ height: 44, maxWidth: '100%', objectFit: 'contain', display: 'block', margin: '0 auto 4px' }} />
                ) : (
                  <div style={{ fontSize: compact ? 16 : 22, marginBottom: 2 }}>{it.emoji || '📦'}</div>
                )}
                <div style={{ fontSize: compact ? 10 : 11 }}>{it.title}</div>
                {it.badge && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{it.badge}</div>}
              </button>
            );
          })}
        </div>
        {pages > 1 && (
          <button type="button" disabled={page >= pages - 1 || busy} onClick={() => setPage(page + 1)} style={arrowStyle(page >= pages - 1)} aria-label="Вперёд">▶</button>
        )}
      </div>
      {pages > 1 && (
        <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{page + 1} / {pages}</div>
      )}
    </div>
  );
}
