import { useCallback, useEffect, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type Pet } from '../api/endpoints';

interface UserPet {
  id: number;
  pet_id: number;
  pet_name: string;
  pet_emoji: string;
  bonus_description: string;
  acquired_at: string;
}

interface DrawnCard {
  color: string;
  value: number;
  is_treasure: boolean;
}

interface SettleResult {
  pet_id: number;
  pet_name: string;
  drawn_cards: DrawnCard[];
  required: number;
}

const TOTAL_SLOTS = 5;
const COLOR_LABEL: Record<string, string> = { green: '🟢', blue: '🔵', violet: '🟣' };

export default function PetsPage() {
  const { refresh, loading: sessionLoading } = useSession();
  const [userPets, setUserPets] = useState<UserPet[]>([]);
  const [catalog, setCatalog] = useState<Pet[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [selectOpen, setSelectOpen] = useState(false);
  const [settleResult, setSettleResult] = useState<SettleResult | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pets, cat] = await Promise.all([
        api.userPets(),
        api.adminPets(),
      ]);
      setUserPets(pets);
      setCatalog(cat);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  const ownedPetIds = new Set(userPets.map((p) => p.pet_id));

  async function doSettle(pet: Pet) {
    setBusy(true); setMsg(null);
    try {
      const result: SettleResult = await api.settlePet(pet.id);
      setSettleResult(result);
      setSelectOpen(false);
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  if (loading) return <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--shell-pad)' }}><div className="fm-card">Загрузка…</div></div>;

  const slots = Array.from({ length: TOTAL_SLOTS }, (_, i) => userPets[i] ?? null);

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ textAlign: 'center' }}>🐾 Поселение питомцев</h1>

      {msg && <div className="fm-card" style={{ marginBottom: 10, fontSize: 14 }}>{msg}</div>}

      <div className="fm-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))' }}>
        {slots.map((pet, i) => (
          <div key={i} className="fm-card fm-rise" style={{ textAlign: 'center', minHeight: 140, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            {pet ? (
              <>
                <div style={{ fontSize: 36 }}>{pet.pet_emoji || '🐾'}</div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{pet.pet_name}</div>
                {pet.bonus_description && (
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{pet.bonus_description}</div>
                )}
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                  {new Date(pet.acquired_at).toLocaleDateString()}
                </div>
              </>
            ) : (
              <button
                className="fm-btn fm-btn-outline"
                style={{ width: '100%', height: '100%', minHeight: 100, fontSize: 28, opacity: 0.5 }}
                onClick={() => {
                  const available = catalog.filter((p) => !ownedPetIds.has(p.id));
                  if (available.length === 0) {
                    setMsg('Все питомцы уже поселены!');
                    return;
                  }
                  setSelectOpen(true);
                }}
              >
                +
              </button>
            )}
          </div>
        ))}
      </div>

      {selectOpen && (
        <Modal title="🐾 Выберите питомца" onClose={() => setSelectOpen(false)}>
          {catalog.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>Каталог питомцев пуст.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {catalog.map((pet) => {
                const owned = ownedPetIds.has(pet.id);
                return (
                  <button
                    key={pet.id}
                    className="fm-card fm-rise"
                    disabled={owned || busy}
                    onClick={() => doSettle(pet)}
                    style={{
                      cursor: owned ? 'default' : 'pointer',
                      opacity: owned ? 0.4 : 1,
                      textAlign: 'left',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '10px 14px',
                    }}
                  >
                    <span style={{ fontSize: 28 }}>{pet.emoji || '🐾'}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{pet.name}</div>
                      {pet.bonus_description && (
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{pet.bonus_description}</div>
                      )}
                      {owned && <div style={{ fontSize: 10, color: 'var(--success)', marginTop: 2 }}>✓ уже поселён</div>}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </Modal>
      )}

      {settleResult && (
        <Modal title={`✨ ${settleResult.pet_name} — карты вытянуты`} onClose={() => setSettleResult(null)}>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 10, textAlign: 'center' }}>
            Вытянуто {settleResult.drawn_cards.length} карт:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center', marginBottom: 14 }}>
            {settleResult.drawn_cards.map((card, idx) => (
              <div
                key={idx}
                className="fm-card"
                style={{
                  width: 56, height: 72, display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center', fontSize: 12,
                  border: card.is_treasure ? '2px solid gold' : undefined,
                  background: card.is_treasure ? 'rgba(255,215,0,0.12)' : undefined,
                }}
              >
                <div style={{ fontSize: 18 }}>{COLOR_LABEL[card.color] || '⚪'}</div>
                <div style={{ fontWeight: 700 }}>{card.value}</div>
                {card.is_treasure && <div style={{ fontSize: 10, color: 'gold' }}>★</div>}
              </div>
            ))}
          </div>
          <div className="fm-card" style={{ textAlign: 'center', background: 'rgba(255,255,255,0.06)', marginBottom: 8 }}>
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Требуется крестиков</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>✕ {settleResult.required}</div>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0, textAlign: 'center' }}>
            Отчитайтесь о вышивке — после зачёта питомец появится в слоте.
          </p>
          <button className="fm-btn" style={{ width: '100%', marginTop: 12 }} onClick={() => setSettleResult(null)}>
            Понятно
          </button>
        </Modal>
      )}
    </div>
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
