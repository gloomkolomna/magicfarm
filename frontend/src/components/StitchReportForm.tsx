import { useState } from 'react';
import { api } from '../api/endpoints';

export default function StitchReportForm({
  contextType,
  contextId,
  cellId,
  required,
  busy,
  onDone,
}: {
  contextType: string;
  contextId: number | null | undefined;
  cellId?: number;
  required?: number | null;
  busy: boolean;
  onDone: () => Promise<void>;
}) {
  const [amount, setAmount] = useState('');
  const [before, setBefore] = useState<File | null>(null);
  const [after, setAfter] = useState<File | null>(null);
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    if (!amount || !before || !after) return;
    setSubmitting(true);
    setErr(null);
    try {
      await api.createStitchReport(
        Number(amount), before, after, note || undefined,
        contextType, contextId ?? undefined, cellId,
      );
      setAmount(''); setBefore(null); setAfter(null); setNote('');
      await onDone();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Не удалось отправить отчёт. Попробуйте ещё раз.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10 }}>
      <strong style={{ fontSize: 14 }}>📷 Отчитаться о вышивке</strong>
      {required != null && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 8px' }}>
          Вышейте норму {required} крестиков, сделайте фото и отправьте отчёт.
        </p>
      )}
      <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Сколько крестиков вышито</label>
      <input className="fm-input" type="number" min={1} value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="например, 150" />
      <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Фото ДО вышивки</label>
      <input type="file" accept="image/*" onChange={(e) => setBefore(e.target.files?.[0] || null)} />
      {before && <div style={{ fontSize: 11, color: '#5f8', marginTop: 2 }}>✓ {before.name}</div>}
      <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Фото ПОСЛЕ вышивки</label>
      <input type="file" accept="image/*" onChange={(e) => setAfter(e.target.files?.[0] || null)} />
      {after && <div style={{ fontSize: 11, color: '#5f8', marginTop: 2 }}>✓ {after.name}</div>}
      <label style={{ display: 'block', margin: '10px 0 6px', fontSize: 14 }}>Заметка (необязательно)</label>
      <input className="fm-input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="что вышили" />
      <button className="fm-btn" style={{ width: '100%', marginTop: 12 }} disabled={busy || submitting || !amount || !before || !after} onClick={submit}>
        Отправить отчёт
      </button>
      {err && <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 8 }}>{err}</div>}
    </div>
  );
}
