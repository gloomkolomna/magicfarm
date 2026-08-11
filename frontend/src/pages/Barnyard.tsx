import { useCallback, useEffect, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type Animal, type BarnyardPen, type BarnyardProduceResult } from '../api/endpoints';

export default function BarnyardPage() {
  const { refresh, loading: sessionLoading } = useSession();
  const [pens, setPens] = useState<BarnyardPen[]>([]);
  const [animals, setAnimals] = useState<Animal[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [installPen, setInstallPen] = useState<BarnyardPen | null>(null);
  const [installAnimalId, setInstallAnimalId] = useState<number | null>(null);

  const [investPen, setInvestPen] = useState<BarnyardPen | null>(null);
  const [investAmount, setInvestAmount] = useState('');

  const [produceResult, setProduceResult] = useState<BarnyardProduceResult | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, a] = await Promise.all([api.barnyardPens(), api.adminAnimals()]);
      setPens(p);
      setAnimals(a);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  async function doInstall() {
    if (!installPen || installAnimalId == null) return;
    setBusy(true); setMsg(null);
    try {
      await api.barnyardInstall(installPen.id, installAnimalId);
      setMsg('✓ Животное установлено!');
      setInstallPen(null); setInstallAnimalId(null);
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doInvest() {
    if (!investPen || !investAmount) return;
    setBusy(true); setMsg(null);
    try {
      await api.barnyardInvest(investPen.id, Number(investAmount));
      setMsg('✓ Крестики вложены');
      setInvestPen(null); setInvestAmount('');
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doProduce(pen: BarnyardPen) {
    setBusy(true); setMsg(null);
    try {
      const result = await api.barnyardProduce(pen.id);
      setProduceResult(result);
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  if (loading) {
    return (
      <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка скотного двора…</div>
      </div>
    );
  }

  const sorted = [...pens].sort((a, b) => a.opening_order - b.opening_order);

  return (
    <>
      <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <h1 style={{ textAlign: 'center' }}>🐄 Скотный двор</h1>

        {msg && <div className="fm-card" style={{ marginBottom: 10, fontSize: 14 }}>{msg}</div>}

        {sorted.length === 0 ? (
          <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
            Загоны не найдены. Обратитесь к админу.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 10 }}>
            {sorted.map((pen) => (
              <div key={pen.id} className="fm-card fm-rise" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                  Загон #{pen.opening_order}
                </div>

                {pen.status === 'empty' && (
                  <>
                    <div style={{ fontSize: 40, lineHeight: 1, marginBottom: 8 }}>🔒</div>
                    <div style={{ color: 'var(--text-muted)', marginBottom: 10 }}>Пусто</div>
                    <button
                      className="fm-btn fm-btn-outline"
                      style={{ width: '100%' }}
                      disabled={busy || animals.length === 0}
                      onClick={() => {
                        setInstallPen(pen);
                        setInstallAnimalId(animals[0]?.id ?? null);
                      }}
                    >
                      🐾 Установить животное
                    </button>
                  </>
                )}

                {pen.status === 'building' && (
                  <>
                    <div style={{ fontSize: 40, lineHeight: 1, marginBottom: 4 }}>
                      {pen.animal_emoji || '🐾'}
                    </div>
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>{pen.animal_name}</div>
                    <div className="fm-progress" style={{ marginBottom: 6 }}>
                      <div
                        className="fm-progress-fill"
                        style={{
                          width: `${pen.required > 0 ? Math.min(100, Math.round((pen.accumulated / pen.required) * 100)) : 0}%`,
                        }}
                      />
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
                      {pen.accumulated}/{pen.required}
                    </div>
                    <button
                      className="fm-btn fm-btn-outline"
                      style={{ width: '100%', marginBottom: 6 }}
                      disabled={busy}
                      onClick={() => {
                        setInvestPen(pen);
                        setInvestAmount(String(Math.max(0, pen.required - pen.accumulated)));
                      }}
                    >
                      💧 Вложить крестики
                    </button>
                  </>
                )}

                {pen.status === 'ready' && (
                  <>
                    <div style={{ fontSize: 40, lineHeight: 1, marginBottom: 4 }}>
                      {pen.animal_emoji || '🐾'}
                    </div>
                    <div style={{ fontWeight: 600, marginBottom: 10 }}>{pen.animal_name}</div>
                    <button
                      className="fm-btn"
                      style={{ width: '100%' }}
                      disabled={busy}
                      onClick={() => doProduce(pen)}
                    >
                      🥚 Получить продукцию
                    </button>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Модалка установки животного */}
      {installPen && (
        <Modal title="🐾 Установить животное" onClose={() => setInstallPen(null)}>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 10 }}>
            Загон #{installPen.opening_order}. Выберите животное из каталога:
          </p>
          {animals.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Каталог животных пуст.</div>
          ) : (
            <select className="fm-input" value={installAnimalId ?? ''} onChange={(e) => setInstallAnimalId(Number(e.target.value))}>
              {animals.map((a) => (
                <option key={a.id} value={a.id}>{a.emoji} {a.name}</option>
              ))}
            </select>
          )}
          <button
            className="fm-btn"
            style={{ width: '100%', marginTop: 14 }}
            disabled={busy || installAnimalId == null}
            onClick={doInstall}
          >
            Установить
          </button>
        </Modal>
      )}

      {/* Модалка вложения крестиков */}
      {investPen && (
        <Modal title={`💧 ${investPen.animal_name}`} onClose={() => setInvestPen(null)}>
          <div className="fm-progress" style={{ marginBottom: 10 }}>
            <div
              className="fm-progress-fill"
              style={{
                width: `${investPen.required > 0 ? Math.min(100, Math.round((investPen.accumulated / investPen.required) * 100)) : 0}%`,
              }}
            />
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 10 }}>
            {investPen.accumulated}/{investPen.required} крестиков
          </div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Вложить крестиков</label>
          <input className="fm-input" type="number" min={1} value={investAmount} onChange={(e) => setInvestAmount(e.target.value)} />
          <button
            className="fm-btn"
            style={{ width: '100%', marginTop: 12 }}
            disabled={busy || !investAmount}
            onClick={doInvest}
          >
            Вложить
          </button>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
            Чтобы пополнить баланс крестиков — отчитайтесь о вышивке в модалке грядки.
          </p>
        </Modal>
      )}

      {/* Модалка результата продукции */}
      {produceResult && (
        <Modal title="🎲 Результат броска" onClose={() => setProduceResult(null)}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 48, lineHeight: 1, marginBottom: 10 }}>
              {produceResult.die}
            </div>
            <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 4 }}>
              {produceResult.animal_name}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 10 }}>
              Норма вышивки: {produceResult.required} крестиков
            </div>
            <div className="fm-chip" style={{ display: 'inline-block', fontSize: 16 }}>
              +{produceResult.product_coins} 🪙
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12 }}>
              Вышейте норму, отчитайтесь о вышивке — и продукция станет доступна.
            </p>
          </div>
        </Modal>
      )}
    </>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: 420, maxHeight: '85vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
