import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, type RemedyLab } from '../api/endpoints';
import Toast from '../components/Toast';

export default function RemedyLabPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [lab, setLab] = useState<RemedyLab | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const fieldId = Number(id);

  const load = useCallback(() => {
    if (!Number.isFinite(fieldId)) return;
    setLoading(true);
    api.remedyLab(fieldId)
      .then(setLab)
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, [fieldId]);

  useEffect(() => { load(); }, [load]);

  async function doBrew(cardId: number, patientName: string) {
    setBusy(cardId);
    setMsg(null);
    try {
      const res = await api.brewRemedy(cardId);
      setMsg(`✓ ${res.remedy_name} сварен! ${patientName} вылечен.`);
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(null);
    }
  }

  if (loading && !lab) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка лаборатории…</div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <button className="fm-btn fm-btn-outline fm-btn-xs" onClick={() => nav('/infirmary')}>← Назад</button>
        <h1 style={{ margin: 0, fontSize: 20, flex: 1 }}>⚗️ {lab?.name}</h1>
      </div>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {lab && (
        <div className="fm-card" style={{ marginBottom: 10, fontSize: 13, color: 'var(--text-secondary)' }}>
          Сварите мазь по карточке рецепта — ингредиенты спишутся со склада, пациент сразу выздоровеет.
        </div>
      )}

      <h3 style={{ margin: '0 0 8px' }}>Карточки рецептов</h3>
      <div className="fm-grid">
        {lab?.remedy_cards.map((card) => (
          <div key={card.id} className="fm-card fm-rise">
            <strong>{card.remedy_name}</strong>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0' }}>
              Пациент: {card.patient_name}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
              {card.recipe_items.map((i) => `${i.ingredient_name} ×${i.qty}`).join(', ')}
            </div>
            <button className="fm-btn fm-btn-sm" style={{ width: '100%' }} disabled={busy === card.id} onClick={() => doBrew(card.id, card.patient_name)}>
              🧪 Сварить
            </button>
          </div>
        ))}
        {(lab?.remedy_cards.length ?? 0) === 0 && (
          <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
            Пока нет карточек рецептов. Поставьте верный диагноз в лечебнице, чтобы получить карточку.
          </div>
        )}
      </div>

      <h3 style={{ margin: '16px 0 8px' }}>Аптекарский склад</h3>
      <div className="fm-grid">
        {(lab?.apothecary ?? []).map((a) => (
          <div key={a.ingredient_id} className="fm-card">
            <strong>{a.name}</strong>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>×{a.qty}</div>
          </div>
        ))}
        {(lab?.apothecary.length ?? 0) === 0 && (
          <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Склад пуст.</div>
        )}
      </div>
    </div>
  );
}
