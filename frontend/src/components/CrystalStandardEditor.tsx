import { useEffect, useState } from 'react';
import { api, type CrystalColor, type CrystalNorms, type NormImage } from '../api/endpoints';
import { mediaUrl } from '../api/media';

const COLORS: { color: CrystalColor; emoji: string; label: string }[] = [
  { color: 'green', emoji: '🟢', label: 'Зелёный' },
  { color: 'blue', emoji: '🔵', label: 'Синий' },
  { color: 'violet', emoji: '🟣', label: 'Фиолетовый' },
];

function cloneNorms(n: CrystalNorms): CrystalNorms {
  return {
    green: { ...n.green },
    blue: { ...n.blue },
    violet: { ...n.violet },
  };
}

export default function CrystalStandardEditor({ disabled }: { disabled: boolean }) {
  const [norms, setNorms] = useState<CrystalNorms | null>(null);
  const [images, setImages] = useState<Record<string, string | null>>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.crystalStandard().then(setNorms).catch(() => {});
    api.normImages().then((list) => {
      const map: Record<string, string | null> = {};
      for (const img of list) {
        map[`${img.color}_${img.count}`] = img.image_url;
      }
      setImages(map);
    }).catch(() => {});
  }, []);

  function setVal(color: CrystalColor, field: 'norm' | 'treasure', raw: string) {
    if (!norms) return;
    const n = cloneNorms(norms);
    n[color][field] = raw === '' ? 0 : Number(raw);
    setNorms(n);
  }

  async function save() {
    if (!norms) return;
    setBusy(true); setMsg(null);
    try {
      const updated = await api.setCrystalStandard(norms);
      setNorms(cloneNorms(updated));
      setMsg('✓ Стандарт сохранён');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function uploadImage(color: string, count: number, file: File) {
    setBusy(true); setMsg(null);
    try {
      const img = await api.uploadNormImage(color, count, file);
      setImages((prev) => ({ ...prev, [`${color}_${count}`]: img.image_url }));
      setMsg('✓ Изображение загружено');
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  if (!norms) return <div className="fm-card">Загрузка норм…</div>;

  const allFilled = COLORS.every((c) => Number(norms[c.color].norm) >= 1);

  return (
    <div className="fm-card fm-rise" style={{ gridColumn: '1 / -1' }}>
      <strong>🧵 Стандарт норм кристаллов</strong>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 10px' }}>
        Норма за 1 кристалл (итог за карту = норма × значение карты). Это стандарт по умолчанию для новых игроков.
      </p>

      {msg && <div style={{ fontSize: 13, marginBottom: 8 }}>{msg}</div>}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: 4 }}>Цвет</th>
              <th style={{ padding: 4, textAlign: 'center' }}>За 1 кристалл</th>
              <th style={{ padding: 4, textAlign: 'center' }}>💎 Сокровище</th>
            </tr>
          </thead>
          <tbody>
            {COLORS.map(({ color, emoji, label }) => {
              const baseImg = images[`${color}_1`];
              const treasureImg = images[`${color}_0`];
              return (
                <tr key={color}>
                  <td style={{ padding: 4 }}>{emoji} {label}</td>
                  <td style={{ padding: 3, textAlign: 'center', verticalAlign: 'top' }}>
                    <input
                      className="fm-input"
                      type="number"
                      min={1}
                      value={norms[color].norm ?? ''}
                      onChange={(e) => setVal(color, 'norm', e.target.value)}
                      style={{ width: 72, textAlign: 'center', padding: '5px 3px' }}
                    />
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                      карта ×5 = {(Number(norms[color].norm) || 0) * 5}
                    </div>
                    {baseImg && (
                      <img src={mediaUrl(baseImg)} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 3, marginTop: 3, display: 'block', marginLeft: 'auto', marginRight: 'auto' }} />
                    )}
                    <label style={{ cursor: 'pointer', fontSize: 11, color: 'var(--text-muted)', marginTop: 2, display: 'inline-block' }}>
                      🖼
                      <input type="file" accept="image/*" style={{ display: 'none' }}
                        onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadImage(color, 1, f); }}
                      />
                    </label>
                  </td>
                  <td style={{ padding: 3, textAlign: 'center', verticalAlign: 'top' }}>
                    <input
                      className="fm-input"
                      type="number"
                      min={0}
                      value={norms[color].treasure ?? 0}
                      onChange={(e) => setVal(color, 'treasure', e.target.value)}
                      style={{ width: 72, textAlign: 'center', padding: '5px 3px' }}
                      placeholder="опц."
                    />
                    {treasureImg && (
                      <img src={mediaUrl(treasureImg)} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 3, marginTop: 3, display: 'block', marginLeft: 'auto', marginRight: 'auto' }} />
                    )}
                    <label style={{ cursor: 'pointer', fontSize: 11, color: 'var(--text-muted)', marginTop: 2, display: 'inline-block' }}>
                      🖼
                      <input type="file" accept="image/*" style={{ display: 'none' }}
                        onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadImage(color, 0, f); }}
                      />
                    </label>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <button className="fm-btn" style={{ marginTop: 12 }} disabled={disabled || busy || !allFilled} onClick={save}>
        Сохранить стандарт
      </button>
    </div>
  );
}
