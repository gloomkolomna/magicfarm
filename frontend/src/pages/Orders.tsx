import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type Order } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';
import SpritePedestal from '../components/SpritePedestal';

const STATUS_LABEL: Record<string, { label: string; emoji: string }> = {
  open: { label: 'Открыт', emoji: '📋' },
  fulfilled: { label: 'Выполнен', emoji: '✅' },
  cancelled: { label: 'Отменён', emoji: '✖️' },
};

const STATUS_COLOR: Record<string, string> = {
  open: 'var(--accent-warm)',
  fulfilled: 'var(--success)',
  cancelled: 'var(--text-muted)',
};

export default function OrdersPage() {
  const { refresh, loading: sessionLoading } = useSession();
  const nav = useNavigate();
  const [orders, setOrders] = useState<Order[]>([]);
  const [inventory, setInventory] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [detailOrder, setDetailOrder] = useState<Order | null>(null);
  const [zoomImg, setZoomImg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ord, inv] = await Promise.all([
        api.orders(), api.inventory().catch(() => []),
      ]);
      setOrders(ord);
      const invMap: Record<number, number> = {};
      for (const i of inv) {
        if (i.item_kind === 'product') invMap[i.item_id] = (invMap[i.item_id] || 0) + i.qty;
      }
      setInventory(invMap);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  async function act(fn: () => Promise<unknown>, okMsg: string): Promise<boolean> {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg('✓ ' + okMsg);
      await load();
      await refresh();
      return true;
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
      return false;
    } finally {
      setBusy(false);
    }
  }

  const openOrders = orders.filter((o) => o.status === 'open');
  const doneOrders = orders.filter((o) => o.status !== 'open');

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      <button
        className="fm-btn"
        style={{ width: '100%', marginBottom: 14 }}
        disabled={busy}
        onClick={() => nav('/orders/catalog')}
      >
        ➕ Взять новый заказ
      </button>

      {loading ? (
        <div className="fm-card">Загрузка заказов…</div>
      ) : (
        <>
          {openOrders.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)', marginBottom: 14 }}>
              Нет активных заказов.
            </div>
          ) : (
            <div className="fm-grid" style={{ marginBottom: 14 }}>
              {openOrders.map((o) => {
                const have = inventory[o.product_id] || 0;
                const need = o.qty;
                const ok = have >= need;
                return (
                  <div key={o.id} className="fm-card fm-rise" style={{ textAlign: 'center', cursor: 'pointer' }} onClick={() => setDetailOrder(o)}>
                    <SpritePedestal url={o.image_url ? mediaUrl(o.image_url) : null} emoji={o.product_emoji} height={110} />
                    <strong style={{ display: 'block', marginBottom: 8 }}>{o.product_name}</strong>
                    {o.name && <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>{o.name}</div>}
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
                      Заказчик: {o.customer || '—'}
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 8,
                        fontSize: 13,
                        borderTop: '1px solid var(--border)',
                        paddingTop: 8,
                      }}
                    >
                      <span style={{ color: ok ? 'var(--success)' : 'var(--danger)', whiteSpace: 'nowrap' }}>
                        {have}/{need} на складе
                      </span>
                      <span style={{ color: 'var(--accent-warm)', fontWeight: 600, whiteSpace: 'nowrap' }}>🪙 {o.reward_coins}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                      <button
                        className="fm-btn fm-btn-sm"
                        style={{ flex: 1 }}
                        disabled={busy}
                        onClick={(e) => { e.stopPropagation(); act(() => api.fulfillOrder(o.id), `Заказ выполнен! +${o.reward_coins} монет`); }}
                      >
                        Выполнить
                      </button>
                      <button
                        className="fm-btn fm-btn-sm fm-btn-outline"
                        disabled={busy}
                        onClick={(e) => { e.stopPropagation(); act(() => api.cancelOrder(o.id), 'Заказ отменён'); }}
                      >
                        Отмена
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {doneOrders.length > 0 && (
            <>
              <h2 style={{ fontSize: 16, margin: '18px 0 10px' }}>История</h2>
              <div className="fm-grid">
                {doneOrders.map((o) => {
                  const s = STATUS_LABEL[o.status] || STATUS_LABEL.open;
                  return (
                    <div key={o.id} className="fm-card" style={{ textAlign: 'center', opacity: 0.8 }}>
                      <SpritePedestal url={o.image_url ? mediaUrl(o.image_url) : null} emoji={o.product_emoji} height={80} onZoom={setZoomImg} />
                      <strong style={{ display: 'block', marginBottom: 6 }}>{o.product_name}</strong>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                        ×{o.qty} · {o.customer || '—'}
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: 6,
                          fontSize: 13,
                          color: STATUS_COLOR[o.status] || 'var(--text-muted)',
                        }}
                      >
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: STATUS_COLOR[o.status] || 'var(--text-muted)', flexShrink: 0 }} />
                        {s.label} {s.emoji}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}

      {detailOrder && (
        <Modal title="Детали заказа" onClose={() => setDetailOrder(null)}>
          <SpritePedestal url={detailOrder.image_url ? mediaUrl(detailOrder.image_url) : null} emoji={detailOrder.product_emoji} height={160} onZoom={setZoomImg} />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <strong style={{ fontSize: 18 }}>{detailOrder.product_name}</strong>
            <span className="fm-chip" style={{ fontSize: 16 }}>×{detailOrder.qty}</span>
          </div>
          <div style={{ fontSize: 14, marginBottom: 4 }}>
            {(() => {
              const have = inventory[detailOrder.product_id] || 0;
              const need = detailOrder.qty;
              const ok = have >= need;
              return <span style={{ color: ok ? 'var(--success)' : 'var(--danger)' }}>На складе: {have} / {need}</span>;
            })()}
          </div>
          {detailOrder.name && (
            <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 4 }}>{detailOrder.name}</div>
          )}
          <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 8 }}>
            Заказчик: {detailOrder.customer}
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: 15,
              borderTop: '1px solid var(--border)',
              paddingTop: 8,
              marginBottom: 14,
            }}
          >
            <span style={{ color: 'var(--text-muted)' }}>Награда</span>
            <span style={{ color: 'var(--accent-warm)', fontWeight: 600 }}>🪙 {detailOrder.reward_coins}</span>
          </div>
          {detailOrder.status === 'open' && (
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="fm-btn"
                style={{ flex: 1 }}
                disabled={busy}
                onClick={() => act(() => api.fulfillOrder(detailOrder.id), `Заказ выполнен! +${detailOrder.reward_coins} монет`)}
              >
                Выполнить
              </button>
              <button
                className="fm-btn fm-btn-outline"
                style={{ flex: 1 }}
                disabled={busy}
                onClick={() => act(() => api.cancelOrder(detailOrder.id), 'Заказ отменён')}
              >
                Отмена
              </button>
            </div>
          )}
        </Modal>
      )}

      {zoomImg && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
          <button
            onClick={() => setZoomImg(null)}
            style={{ position: 'absolute', top: 16, right: 16, zIndex: 1, fontSize: 24, background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: '8px 12px' }}
          >
            ✕
          </button>
          <img src={zoomImg} alt="" style={{ maxWidth: '90vw', maxHeight: '90vh', objectFit: 'contain' }} onClick={(e) => e.stopPropagation()} />
        </div>
      )}
    </div>
  );
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 60,
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(3px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
    >
      <div
        className="fm-card fm-rise"
        onClick={(e) => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 'calc(var(--shell-max-width) * 0.767)', maxHeight: '85vh', overflowY: 'auto' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
