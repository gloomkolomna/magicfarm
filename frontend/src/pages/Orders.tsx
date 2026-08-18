import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type Order, type UserPotion } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';
import SpritePedestal from '../components/SpritePedestal';

export default function OrdersPage() {
  const { refresh, loading: sessionLoading } = useSession();
  const nav = useNavigate();
  const [orders, setOrders] = useState<Order[]>([]);
  const [inventory, setInventory] = useState<Record<number, number>>({});
  const [potions, setPotions] = useState<UserPotion[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [detailOrder, setDetailOrder] = useState<Order | null>(null);
  const [zoomImg, setZoomImg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ord, inv, pots] = await Promise.all([
        api.orders(), api.inventory().catch(() => []), api.userPotions().catch(() => [] as UserPotion[]),
      ]);
      setOrders(ord);
      const invMap: Record<number, number> = {};
      for (const i of inv) {
        if (i.item_kind === 'product') invMap[i.item_id] = (invMap[i.item_id] || 0) + i.qty;
      }
      setInventory(invMap);
      setPotions(pots);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка загрузки'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  function haveFor(o: Order): number {
    if (o.potion_recipe_id != null) {
      return potions.some((p) => p.potion_recipe_id === o.potion_recipe_id && !p.used) ? 1 : 0;
    }
    return inventory[o.product_id ?? -1] || 0;
  }

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
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14 }}>
              {openOrders.map((o) => {
                const have = haveFor(o);
                const need = o.qty;
                const ok = have >= need;
                const orderImg = o.image_url || o.product_image_url || o.potion_image_url;
                return (
                  <div key={o.id} className="fm-card fm-rise" style={{ cursor: 'pointer' }} onClick={() => setDetailOrder(o)}>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                      {o.customer_image_url ? (
                        <img
                          src={mediaUrl(o.customer_image_url)}
                          alt=""
                          style={{ maxHeight: 64, maxWidth: 140, width: 'auto', height: 'auto', objectFit: 'contain', borderRadius: 8, flexShrink: 0, cursor: 'zoom-in' }}
                          onClick={(e) => { e.stopPropagation(); setZoomImg(mediaUrl(o.customer_image_url!)); }}
                        />
                      ) : (
                        <div
                          style={{
                            width: 48, height: 48, borderRadius: 8, flexShrink: 0,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 24, background: 'var(--bg-secondary, rgba(0,0,0,0.08))',
                            border: '2px solid var(--border)',
                          }}
                        >
                          🧑
                        </div>
                      )}
                      <div style={{ minWidth: 0 }}>
                        <strong style={{ display: 'block', fontSize: 15 }}>{o.customer || 'Заказчик не указан'}</strong>
                        {o.customer_phrase && (
                          <div style={{ fontSize: 13, fontStyle: 'italic', color: 'var(--text-secondary)', marginTop: 2 }}>
                            «{o.customer_phrase}»
                          </div>
                        )}
                      </div>
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
                        marginTop: 10,
                      }}
                    >
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                        {orderImg ? (
                          <img
                            src={mediaUrl(orderImg)}
                            alt=""
                            style={{ height: 40, maxWidth: 64, width: 'auto', objectFit: 'contain', borderRadius: 6, flexShrink: 0, cursor: 'zoom-in' }}
                            onClick={(e) => { e.stopPropagation(); setZoomImg(mediaUrl(orderImg!)); }}
                          />
                        ) : (
                          <span style={{ fontSize: 17 }}>{o.product_emoji || '📦'}</span>
                        )}
                        <strong style={{ whiteSpace: 'nowrap' }}>{o.product_name}</strong>
                        <span className="fm-chip" style={{ fontSize: 12 }}>×{need}</span>
                      </span>
                      <span style={{ color: ok ? 'var(--success)' : 'var(--danger)', whiteSpace: 'nowrap' }}>
                        {have}/{need} {o.potion_recipe_id != null ? 'зелье' : 'на складе'}
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
        </>
      )}

      {detailOrder && (
        <Modal title="Детали заказа" onClose={() => setDetailOrder(null)}>
          <SpritePedestal url={(detailOrder.image_url || detailOrder.product_image_url || detailOrder.potion_image_url) ? mediaUrl(detailOrder.image_url || detailOrder.product_image_url || detailOrder.potion_image_url) : null} emoji={detailOrder.product_emoji} height={160} onZoom={setZoomImg} />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <strong style={{ fontSize: 18 }}>{detailOrder.potion_recipe_id != null ? `🧪 ${detailOrder.potion_name}` : detailOrder.product_name}</strong>
            <span className="fm-chip" style={{ fontSize: 16 }}>×{detailOrder.qty}</span>
          </div>
          <div style={{ fontSize: 14, marginBottom: 4 }}>
            {(() => {
              const have = haveFor(detailOrder);
              const need = detailOrder.qty;
              const ok = have >= need;
              return <span style={{ color: ok ? 'var(--success)' : 'var(--danger)' }}>{detailOrder.potion_recipe_id != null ? 'Зелье в котле' : 'На складе'}: {have} / {need}</span>;
            })()}
          </div>
          {detailOrder.name && (
            <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 4 }}>{detailOrder.name}</div>
          )}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 8 }}>
            {detailOrder.customer_image_url ? (
              <img
                src={mediaUrl(detailOrder.customer_image_url)}
                alt=""
                style={{ maxHeight: 96, maxWidth: 160, width: 'auto', height: 'auto', objectFit: 'contain', borderRadius: 8, flexShrink: 0, cursor: 'zoom-in' }}
                onClick={() => setZoomImg(mediaUrl(detailOrder.customer_image_url!))}
              />
            ) : (
              <div
                style={{
                  width: 44, height: 44, borderRadius: 8, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 20, background: 'var(--bg-secondary, rgba(0,0,0,0.08))',
                  border: '2px solid var(--border)',
                }}
              >
                🧑
              </div>
            )}
            <div style={{ minWidth: 0 }}>
              <strong style={{ display: 'block' }}>{detailOrder.customer || 'Заказчик не указан'}</strong>
              {detailOrder.customer_phrase && (
                <div style={{ fontSize: 13, fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                  «{detailOrder.customer_phrase}»
                </div>
              )}
            </div>
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
                onClick={async () => {
                  const okDone = await act(() => api.fulfillOrder(detailOrder.id), `Заказ выполнен! +${detailOrder.reward_coins} монет`);
                  if (okDone) setDetailOrder(null);
                }}
              >
                Выполнить
              </button>
              <button
                className="fm-btn fm-btn-outline"
                style={{ flex: 1 }}
                disabled={busy}
                onClick={async () => {
                  const okDone = await act(() => api.cancelOrder(detailOrder.id), 'Заказ отменён — он снова доступен в каталоге');
                  if (okDone) setDetailOrder(null);
                }}
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
