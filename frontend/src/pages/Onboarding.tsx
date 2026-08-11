import { useEffect, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type CrystalColor, type CrystalNorms, type CrystalPreset } from '../api/endpoints';

const COLORS: { color: CrystalColor; emoji: string; label: string }[] = [
  { color: 'green', emoji: '🟢', label: 'Зелёный' },
  { color: 'blue', emoji: '🔵', label: 'Синий' },
  { color: 'violet', emoji: '🟣', label: 'Фиолетовый' },
];

const COUNTS = [1, 2, 3, 4, 5, 0];
const COUNT_LABEL: Record<number, string> = { 0: '💎', 1: '×1', 2: '×2', 3: '×3', 4: '×4', 5: '×5' };

function emptyNorms(): CrystalNorms {
  return { green: {}, blue: {}, violet: {} };
}

function cloneNorms(n: CrystalNorms): CrystalNorms {
  return {
    green: { ...n.green },
    blue: { ...n.blue },
    violet: { ...n.violet },
  };
}

export default function Onboarding({ onSaved }: { onSaved?: () => void }) {
  const { refresh } = useSession();
  const [presetMap, setPresetMap] = useState<Record<number, CrystalNorms>>({});
  const [norms, setNorms] = useState<CrystalNorms>(emptyNorms());
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  function presetToNorms(p: CrystalPreset): CrystalNorms {
    const out = emptyNorms();
    (['green', 'blue', 'violet'] as CrystalColor[]).forEach((color) => {
      out[color] = {};
      COUNTS.forEach((cnt) => {
        out[color][cnt] = Number(p.norms[color]?.[String(cnt)] ?? p.norms[color]?.[cnt] ?? 0);
      });
    });
    return out;
  }

  useEffect(() => {
    Promise.all([api.crystalPresets(), api.crystalStandard(), api.myCrystalNorms()])
      .then(([ps, std, mine]) => {
        const map: Record<number, CrystalNorms> = {};
        ps.forEach((p) => { map[p.variant] = presetToNorms(p); });
        setPresetMap(map);
        setNorms(mine.onboarding_done ? cloneNorms(mine.norms) : cloneNorms(std));
      })
      .catch((e: any) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки')))
      .finally(() => setLoaded(true));
  }, []);

  function setVal(color: CrystalColor, count: number, raw: string) {
    const n = cloneNorms(norms);
    const v = raw === '' ? '' : Number(raw);
    n[color][count] = v as number;
    setNorms(n);
  }

  function applyPreset(n: number) {
    const src = presetMap[n];
    if (!src) return;
    setNorms(cloneNorms(src));
    setMsg(null);
  }

  function takeStandard() {
    setBusy(true);
    api
      .crystalStandard()
      .then((std) => {
        setNorms(cloneNorms(std));
        setMsg(null);
      })
      .catch((e: any) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setBusy(false));
  }

  function save() {
    setBusy(true);
    api
      .setMyCrystalNorms(norms)
      .then(async () => {
        if (onSaved) onSaved();
        else await refresh();
        setMsg('✓ Нормы сохранены');
      })
      .catch((e: any) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setBusy(false));
  }

  const allFilled = COLORS.every((c) => COUNTS.filter((cnt) => cnt > 0).every((cnt) => Number(norms[c.color][cnt]) >= 1));

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: 14, marginBottom: 16 }}>
        Каждое растение и товар требует норму вышивки, измеряемую в крестиках.
        Норма считается по картам кристаллов: 3 цвета (🟢🔵🟣) и количество кристаллов (1–5).
        Здесь вы задаёте <strong>цену одного кристалла</strong> каждого цвета — итог за карту
        показан под полем (цена × количество). Потом это можно изменить в любой момент.
      </p>

      {msg && <div className="fm-card" style={{ marginBottom: 10, fontSize: 14 }}>{msg}</div>}

      <div className="fm-card" style={{ marginBottom: 14 }}>
        <strong>Заполнить готовым набором:</strong>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
          <button className="fm-btn fm-btn-outline" style={{ flex: '1 1 auto' }} disabled={busy} onClick={takeStandard}>
            ✓ Стандарт админа
          </button>
          {Object.keys(presetMap).map((k) => (
            <button
              key={k}
              className="fm-btn fm-btn-outline"
              style={{ minWidth: 64 }}
              onClick={() => applyPreset(Number(k))}
              title={`Заполнить пресет ${k}`}
            >
              Пресет {k}
            </button>
          ))}
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8, marginBottom: 0 }}>
          Кнопки только заполняют таблицу для предпросмотра. Изменения применяются кнопкой «Сохранить» ниже.
        </p>
      </div>

      {loaded && (
        <>
          <div className="fm-card" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: 6 }}>Цвет</th>
                  {COUNTS.map((c) => (
                    <th key={c} style={{ padding: 6, textAlign: 'center' }}>{COUNT_LABEL[c]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COLORS.map(({ color, emoji, label }) => (
                  <tr key={color}>
                    <td style={{ padding: 6 }}>
                      {emoji} {label}
                    </td>
                    {COUNTS.map((cnt) => {
                      const isTreasure = cnt === 0;
                      const val = norms[color][cnt];
                      const num = Number(val);
                      const total = !isTreasure && Number.isFinite(num) && num >= 1 ? num * cnt : null;
                      return (
                        <td key={cnt} style={{ padding: 4, textAlign: 'center' }}>
                          <input
                            className="fm-input"
                            type="number"
                            min={isTreasure ? 0 : 1}
                            value={val ?? ''}
                            onChange={(e) => setVal(color, cnt, e.target.value)}
                            style={{ width: isTreasure ? 60 : 56, textAlign: 'center', padding: '6px 4px' }}
                            placeholder={isTreasure ? 'опц.' : ''}
                          />
                          {total !== null && (
                            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                              = {total}
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '8px 0 0' }}>
              Под полем — итог за карту (норма × количество кристаллов).
            </p>
          </div>

          <button
            className="fm-btn"
            style={{ width: '100%', marginTop: 16 }}
            disabled={busy || !allFilled}
            onClick={save}
          >
            Сохранить мои нормы
          </button>
          {!allFilled && (
            <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', marginTop: 6 }}>
              Заполните все 15 полей значениями от 1.
            </p>
          )}
        </>
      )}
    </div>
  );
}
