import { useEffect, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type CrystalColor, type CrystalNorms } from '../api/endpoints';
import Toast from '../components/Toast';

const COLORS: { color: CrystalColor; emoji: string; label: string }[] = [
  { color: 'green', emoji: '🟢', label: 'Зелёный' },
  { color: 'blue', emoji: '🔵', label: 'Синий' },
  { color: 'violet', emoji: '🟣', label: 'Фиолетовый' },
];

function emptyNorms(): CrystalNorms {
  return {
    green: { norm: 0, treasure: 0 },
    blue: { norm: 0, treasure: 0 },
    violet: { norm: 0, treasure: 0 },
  };
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
  const [norms, setNorms] = useState<CrystalNorms>(emptyNorms());
  const [diceNorm, setDiceNorm] = useState<number | ''>('');
  const [animalProductNorm, setAnimalProductNorm] = useState<number | ''>('');
  const [studyNorms, setStudyNorms] = useState<{ level1: number | ''; level2: number | ''; level3: number | '' }>({ level1: '', level2: '', level3: '' });
  const [productionNorms, setProductionNorms] = useState<{ level1: number | ''; level2: number | ''; level3: number | '' }>({ level1: '', level2: '', level3: '' });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.all([api.crystalStandard(), api.myCrystalNorms()])
      .then(([std, mine]) => {
        setNorms(mine.onboarding_done ? cloneNorms(mine.norms) : cloneNorms(std));
        setDiceNorm(mine.dice_norm ?? 200);
        setAnimalProductNorm(mine.animal_product_norm ?? 100);
        const toField = (v: number | null) => (v == null ? '' : v);
        setStudyNorms({
          level1: toField(mine.study_norms?.level1),
          level2: toField(mine.study_norms?.level2),
          level3: toField(mine.study_norms?.level3),
        });
        setProductionNorms({
          level1: toField(mine.production_norms?.level1),
          level2: toField(mine.production_norms?.level2),
          level3: toField(mine.production_norms?.level3),
        });
      })
      .catch((e: any) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки')))
      .finally(() => setLoaded(true));
  }, []);

  function setVal(color: CrystalColor, field: 'norm' | 'treasure', raw: string) {
    const n = cloneNorms(norms);
    n[color][field] = raw === '' ? 0 : Number(raw);
    setNorms(n);
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
    const toNum = (v: number | '') => (v === '' ? null : Number(v));
    api
      .setMyCrystalNorms(
        norms,
        Number(diceNorm) || 200,
        Number(animalProductNorm) || undefined,
        {
          level1: toNum(studyNorms.level1),
          level2: toNum(studyNorms.level2),
          level3: toNum(studyNorms.level3),
        },
        {
          level1: toNum(productionNorms.level1),
          level2: toNum(productionNorms.level2),
          level3: toNum(productionNorms.level3),
        },
      )
      .then(async () => {
        if (onSaved) onSaved();
        else await refresh();
        setMsg('✓ Нормы сохранены');
      })
      .catch((e: any) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setBusy(false));
  }

  const allFilled = COLORS.every((c) => Number(norms[c.color].norm) >= 1) && Number(diceNorm) >= 1;

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: 14, marginBottom: 16 }}>
        Каждое растение и товар требует норму вышивки, измеряемую в крестиках.
        Здесь вы задаёте <strong>цену одного кристалла</strong> каждого цвета — итог за карту
        считается как цена × значение карты (1–5), а при нескольких картах складывается.
        Ниже — ваша норма за одну точку кубика. Потом всё это можно изменить в любой момент.
      </p>

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      <div className="fm-card" style={{ marginBottom: 14 }}>
        <strong>Заполнить стандартом админа:</strong>
        <div style={{ marginTop: 10 }}>
          <button className="fm-btn fm-btn-outline" style={{ width: '100%' }} disabled={busy} onClick={takeStandard}>
            ✓ Стандарт админа
          </button>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8, marginBottom: 0 }}>
          Кнопка только заполняет поля для предпросмотра. Изменения применяются кнопкой «Сохранить» ниже.
        </p>
      </div>

      {loaded && (
        <>
          <div className="fm-card" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: 6 }}>Цвет</th>
                  <th style={{ padding: 6, textAlign: 'center' }}>За 1 кристалл</th>
                  <th style={{ padding: 6, textAlign: 'center' }}>💎 Сокровище</th>
                </tr>
              </thead>
              <tbody>
                {COLORS.map(({ color, emoji, label }) => {
                  const num = Number(norms[color].norm);
                  return (
                    <tr key={color}>
                      <td style={{ padding: 6 }}>{emoji} {label}</td>
                      <td style={{ padding: 4, textAlign: 'center' }}>
                        <input
                          className="fm-input"
                          type="number"
                          min={1}
                          value={norms[color].norm ?? ''}
                          onChange={(e) => setVal(color, 'norm', e.target.value)}
                          style={{ width: 76, textAlign: 'center', padding: '6px 4px' }}
                        />
                        {num >= 1 && (
                          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                            карта ×5 = {num * 5}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: 4, textAlign: 'center' }}>
                        <input
                          className="fm-input"
                          type="number"
                          min={0}
                          value={norms[color].treasure ?? 0}
                          onChange={(e) => setVal(color, 'treasure', e.target.value)}
                          style={{ width: 76, textAlign: 'center', padding: '6px 4px' }}
                          placeholder="опц."
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '8px 0 0' }}>
              Под полем — итог за карту ×5 (норма × значение карты). Сокровище 💎 — фиксированная норма за карту-сокровище.
            </p>
          </div>

          <div className="fm-card" style={{ marginTop: 14, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div>
              <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>🎲 Норма за 1 точку кубика</label>
              <input
                className="fm-input"
                type="number"
                min={1}
                value={diceNorm}
                onChange={(e) => setDiceNorm(e.target.value === '' ? '' : Number(e.target.value))}
                style={{ width: 100, textAlign: 'center' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>🐄 Норма продукции скотного двора</label>
              <input
                className="fm-input"
                type="number"
                min={1}
                value={animalProductNorm}
                onChange={(e) => setAnimalProductNorm(e.target.value === '' ? '' : Number(e.target.value))}
                style={{ width: 100, textAlign: 'center' }}
              />
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0, flex: 1, minWidth: 180 }}>
              Норма для кубиков = это значение × выпавшая грань (дом ведьмы). Норма продукции скотного двора — крестиков за 1 единицу при заборе продукции со склада шатра.
            </p>
          </div>

          <div className="fm-card" style={{ marginTop: 14 }}>
            <strong style={{ fontSize: 14 }}>📖 Нормы изучения рецептов</strong>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 8px' }}>
              Норма вышивки для изучения рецепта соответствующего уровня (уровень растения). Пока не задана — изучение недоступно.
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {([1, 2, 3] as const).map((lvl) => (
                <div key={lvl}>
                  <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>Ур. {lvl}</label>
                  <input
                    className="fm-input"
                    type="number"
                    min={1}
                    placeholder="—"
                    value={studyNorms[`level${lvl}` as 'level1' | 'level2' | 'level3']}
                    onChange={(e) => setStudyNorms({ ...studyNorms, [`level${lvl}`]: e.target.value === '' ? '' : Number(e.target.value) } as typeof studyNorms)}
                    style={{ width: 90, textAlign: 'center' }}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="fm-card" style={{ marginTop: 14 }}>
            <strong style={{ fontSize: 14 }}>🏭 Нормы производства товара</strong>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 8px' }}>
              Норма переработки растения соответствующего уровня. Считается как (кристалл переработки шатра + уровень растения) × норма × количество. Пока не задана — крафт недоступен.
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {([1, 2, 3] as const).map((lvl) => (
                <div key={lvl}>
                  <label style={{ display: 'block', fontSize: 13, marginBottom: 2 }}>Ур. {lvl}</label>
                  <input
                    className="fm-input"
                    type="number"
                    min={1}
                    placeholder="—"
                    value={productionNorms[`level${lvl}` as 'level1' | 'level2' | 'level3']}
                    onChange={(e) => setProductionNorms({ ...productionNorms, [`level${lvl}`]: e.target.value === '' ? '' : Number(e.target.value) } as typeof productionNorms)}
                    style={{ width: 90, textAlign: 'center' }}
                  />
                </div>
              ))}
            </div>
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
              Заполните норму каждого цвета (от 1) и норму кубика (от 1).
            </p>
          )}
        </>
      )}
    </div>
  );
}
