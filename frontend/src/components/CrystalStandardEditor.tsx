import { useEffect, useState } from 'react';
import { api, type CrystalColor, type CrystalNorms, type NormImage } from '../api/endpoints';
import { mediaUrl } from '../api/media';

const COLORS: { color: CrystalColor; emoji: string; label: string }[] = [
  { color: 'green', emoji: '🟢', label: 'Зелёный' },
  { color: 'blue', emoji: '🔵', label: 'Синий' },
  { color: 'violet', emoji: '🟣', label: 'Фиолетовый' },
];

const COUNTS = [1, 2, 3, 4, 5, 0];
const COUNT_LABEL: Record<number, string> = { 0: '💎', 1: '×1', 2: '×2', 3: '×3', 4: '×4', 5: '×5' };

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

  function setVal(color: CrystalColor, count: number, raw: string) {
    if (!norms) return;
    const n = cloneNorms(norms);
    n[color][count] = raw === '' ? (count === 0 ? 0 : (0 as number)) : Number(raw);
    setNorms(n);
  }

  async function applyPreset(preset: number) {
    setBusy(true); setMsg(null);
    try {
      const updated = await api.setCrystalStandardPreset(preset);
      setNorms(cloneNorms(updated));
      setMsg('✓ Применён пресет ' + preset);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
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

  const allFilled = COLORS.every((c) => COUNTS.filter((cnt) => cnt > 0).every((cnt) => Number(norms[c.color][cnt]) >= 1));

  return (
    <div className="fm-card fm-rise" style={{ gridColumn: '1 / -1' }}>
      <strong>🧵 Стандарт норм кристаллов</strong>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 10px' }}>
        Норма за 1 кристалл. Это стандарт по умолчанию для новых игроков.
      </p>

      {msg && <div style={{ fontSize: 13, marginBottom: 8 }}>{msg}</div>}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
        {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
          <button key={n} className="fm-btn fm-btn-outline fm-btn-sm" disabled={disabled || busy} onClick={() => applyPreset(n)}>
            Пресет {n}
          </button>
        ))}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: 4 }}>Цвет</th>
              {COUNTS.map((c) => (
                <th key={c} style={{ padding: 4, textAlign: 'center' }}>{COUNT_LABEL[c]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COLORS.map(({ color, emoji, label }) => (
              <tr key={color}>
                <td style={{ padding: 4 }}>{emoji} {label}</td>
                {COUNTS.map((cnt) => {
                  const val = norms[color][cnt] ?? (cnt === 0 ? 0 : '');
                  const isTreasure = cnt === 0;
                  const total = !isTreasure && Number(val) >= 1 ? Number(val) * cnt : null;
                  const imgKey = `${color}_${cnt}`;
                  const imgUrl = images[imgKey];
                  return (
                    <td key={cnt} style={{ padding: 3, textAlign: 'center', verticalAlign: 'top' }}>
                      <input
                        className="fm-input"
                        type="number"
                        min={isTreasure ? 0 : 1}
                        value={val ?? ''}
                        onChange={(e) => setVal(color, cnt, e.target.value)}
                        style={{ width: isTreasure ? 60 : 52, textAlign: 'center', padding: '5px 3px' }}
                        placeholder={isTreasure ? 'опц.' : ''}
                      />
                      {!isTreasure && total !== null && (
                        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>= {total}</div>
                      )}
                      {imgUrl && (
                        <img src={mediaUrl(imgUrl)} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 3, marginTop: 3, display: 'block', marginLeft: 'auto', marginRight: 'auto' }} />
                      )}
                      <label style={{ cursor: 'pointer', fontSize: 11, color: 'var(--text-muted)', marginTop: 2, display: 'inline-block' }}>
                        🖼
                        <input type="file" accept="image/*" style={{ display: 'none' }}
                          onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadImage(color, cnt, f); }}
                        />
                      </label>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button className="fm-btn" style={{ marginTop: 12 }} disabled={disabled || busy || !allFilled} onClick={save}>
        Сохранить стандарт
      </button>
    </div>
  );
}
