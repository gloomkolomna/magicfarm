import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type Notification } from '../api/endpoints';

function fmt(iso: string): string {
  if (!iso) return '';
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const d = new Date(hasZone ? iso : iso + 'Z');
  return d.toLocaleString('ru-RU', { timeZone: 'Europe/Moscow', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export default function NotificationsPage() {
  const nav = useNavigate();
  const [items, setItems] = useState<Notification[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    api.notifications()
      .then((n) => setItems(n.filter((x) => !x.read)))
      .catch(() => setMsg('Ошибка загрузки уведомлений'));
  }, []);

  async function clearAll() {
    setClearing(true);
    try {
      await api.markNotificationsRead();
      setItems([]);
    } catch {
      setMsg('Ошибка очистки уведомлений');
    } finally {
      setClearing(false);
    }
  }

  function open(n: Notification) {
    setItems((prev) => (prev ? prev.filter((x) => x.id !== n.id) : prev));
    api.markNotificationRead(n.id).catch(() => {});
    if (n.kind === 'trades') {
      nav('/trades');
    } else if (n.kind === 'board') {
      nav('/board');
    } else if (n.peer_vk_id != null) {
      nav(`/chat/${n.peer_vk_id}`);
    }
  }

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '0 0 10px' }}>
        <h1 style={{ fontSize: 20, margin: 0 }}>🔔 Уведомления</h1>
        {items && items.length > 0 && (
          <button className="fm-btn fm-btn-sm fm-btn-outline" style={{ marginLeft: 'auto' }} disabled={clearing} onClick={clearAll}>Очистить</button>
        )}
      </div>
      {msg && <div style={{ fontSize: 13, color: 'var(--danger)', marginBottom: 10 }}>{msg}</div>}
      {items === null ? (
        <div className="fm-card">Загрузка…</div>
      ) : items.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Уведомлений пока нет.</div>
      ) : (
        <div className="fm-grid">
          {items.map((n) => (
            <button
              key={n.id}
              className="fm-card fm-rise"
              style={{
                fontSize: 14,
                textAlign: 'left',
                cursor: n.kind === 'trades' || n.kind === 'board' || n.peer_vk_id != null ? 'pointer' : 'default',
                opacity: n.read ? 0.8 : 1,
                borderColor: n.read ? undefined : 'rgba(255,200,90,0.4)',
              }}
              onClick={() => open(n)}
            >
              <div style={{ whiteSpace: 'pre-wrap' }}>{n.text}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                {fmt(n.created_at)}{n.kind === 'trades' ? ' · нажмите, чтобы открыть бартер →' : n.kind === 'board' ? ' · нажмите, чтобы открыть доску →' : n.peer_vk_id != null ? ' · нажмите, чтобы открыть чат →' : ''}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
