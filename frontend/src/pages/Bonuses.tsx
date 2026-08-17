import { useCallback, useEffect, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type UserPotion, type BonusCatalogItem } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';
import SpritePedestal from '../components/SpritePedestal';

export default function BonusesPage() {
  const { refresh, loading: sessionLoading } = useSession();
  const [userPotions, setUserPotions] = useState<UserPotion[]>([]);
  const [bonuses, setBonuses] = useState<BonusCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [zoomedImg, setZoomedImg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pots, bns] = await Promise.all([
        api.userPotions().catch(() => [] as UserPotion[]),
        api.potionBonuses().catch(() => [] as BonusCatalogItem[]),
      ]);
      setUserPotions(pots);
      setBonuses(bns);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  async function activatePotion(id: number) {
    setBusy(true);
    setMsg(null);
    try {
      const p = await api.activatePotion(id);
      setMsg(`✓ Бонус активирован! ${p.when_fires || 'Сработает автоматически при подходящем действии.'}`);
      const pots = await api.userPotions();
      setUserPotions(pots);
      setBonuses(await api.potionBonuses().catch(() => [] as BonusCatalogItem[]));
      await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setBusy(false);
    }
  }

  const activeBonuses = bonuses.filter((b) => b.activated && !b.used);

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {loading ? (
        <div className="fm-card">Загрузка…</div>
      ) : (
        <>
          {activeBonuses.length > 0 && (
            <div className="fm-card" style={{ marginBottom: 14, background: 'rgba(160,120,220,0.12)', border: '1px solid #a078dc' }}>
              <strong style={{ display: 'block', marginBottom: 8, color: '#c9a6f2' }}>⚡ Активные бонусы</strong>
              {activeBonuses.map((b) => (
                <div key={b.code} style={{ marginBottom: 10 }}>
                  <span className="fm-chip" style={{ background: 'rgba(160,120,220,0.25)', color: '#e6d9ff', border: '1px solid #a078dc' }}>
                    {b.label}
                  </span>
                  {b.when_fires && (
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{b.when_fires}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          <h2 style={{ fontSize: 16, marginBottom: 10 }}>Мои зелья</h2>
          {userPotions.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
              Зелий пока нет. Сварите зелье на странице «Зелья».
            </div>
          ) : (
            <div className="fm-grid" style={{ marginBottom: 16 }}>
              {userPotions.map((p) => (
                <div key={p.id} className="fm-card fm-rise" style={{ textAlign: 'center', opacity: p.used ? 0.6 : p.activated ? 0.7 : 1 }}>
                  {p.image_url && (
                    <SpritePedestal url={mediaUrl(p.image_url)} height={96} onZoom={setZoomedImg} />
                  )}
                  <strong style={{ display: 'block', marginBottom: 8 }}>{p.potion_name}</strong>
                  {(p.bonus_description || p.bonus_code) && (
                    <div
                      style={{
                        fontSize: 13,
                        textAlign: 'left',
                        borderLeft: '3px solid #a078dc',
                        paddingLeft: 8,
                        color: '#c9a6f2',
                      }}
                    >
                      ⚡ {p.bonus_description || p.bonus_code}
                    </div>
                  )}
                  {p.when_fires && (
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '6px 0 0' }}>{p.when_fires}</div>
                  )}
                  <div
                    style={{
                      marginTop: 8,
                      fontSize: 13,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                      color: p.used ? 'var(--text-muted)' : p.activated ? 'var(--success)' : 'var(--text-muted)',
                    }}
                  >
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: p.used ? 'var(--text-muted)' : p.activated ? 'var(--success)' : 'var(--text-muted)',
                        flexShrink: 0,
                      }}
                    />
                    {p.used ? 'Использовано' : p.activated ? 'Активно' : 'Неактивно'}
                  </div>
                  {p.description && (
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '8px 0 0' }}>{p.description}</p>
                  )}
                  {!p.activated && !p.used && (
                    <button
                      className="fm-btn fm-btn-sm fm-btn-wrap"
                      style={{ width: '100%', marginTop: 8 }}
                      disabled={busy}
                      onClick={() => activatePotion(p.id)}
                    >
                      Активировать бонус
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {bonuses.length > 0 && (
            <>
              <h2 style={{ fontSize: 16, margin: '18px 0 10px' }}>Все бонусы</h2>
              <div className="fm-grid">
                {bonuses.map((b) => (
                  <div key={b.code} className="fm-card" style={{ textAlign: 'center', opacity: b.used ? 0.6 : 1 }}>
                    <div style={{ fontSize: 12, color: b.kind === 'instant' ? 'var(--accent-warm)' : '#c9a6f2', marginBottom: 4 }}>
                      {b.kind === 'instant' ? '⚡ Мгновенный' : '♻ Действует раз'}
                    </div>
                    <strong style={{ display: 'block', marginBottom: 8 }}>{b.label}</strong>
                    {b.when_fires && (
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>{b.when_fires}</div>
                    )}
                    {!b.owned ? (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Нет зелья</div>
                    ) : b.used ? (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Использовано</div>
                    ) : b.activated ? (
                      <div style={{ fontSize: 12, color: 'var(--success)' }}>Активен</div>
                    ) : (
                      <button
                        className="fm-btn fm-btn-sm fm-btn-wrap"
                        style={{ width: '100%', marginTop: 8 }}
                        disabled={busy || b.potion_id == null}
                        onClick={() => activatePotion(b.potion_id!)}
                      >
                        Активировать
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}

      {zoomedImg && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
          onClick={() => setZoomedImg(null)}
        >
          <img src={zoomedImg} alt="" style={{ maxWidth: '90vw', maxHeight: '80vh', borderRadius: 10 }} />
        </div>
      )}
    </div>
  );
}
