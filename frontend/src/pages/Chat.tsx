import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type ChatMessage, type Conversation } from '../api/endpoints';
import Toast from '../components/Toast';

function fmt(iso: string | null): string {
  if (!iso) return '';
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const d = new Date(hasZone ? iso : iso + 'Z');
  return d.toLocaleString('ru-RU', { timeZone: 'Europe/Moscow', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export default function ChatPage() {
  const nav = useNavigate();
  const { vkId } = useParams<{ vkId: string }>();
  const { user } = useSession();
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [peer, setPeer] = useState<Conversation | null>(null);
  const [thread, setThread] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const openedPeerRef = useRef<number | null>(null);

  useEffect(() => {
    api.chatConversations().then(setConvs).catch(() => {});
    const id = setInterval(() => {
      api.chatConversations().then(setConvs).catch(() => {});
    }, 15000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!vkId) return;
    const id = Number(vkId);
    if (!id || openedPeerRef.current === id) return;
    openedPeerRef.current = id;
    const buildPeer = (displayName: string) => {
      setPeer({ vk_id: id, display_name: displayName, last_message: '', last_message_at: null, unread_count: 0 });
    };
    api.playerFarm(id)
      .then((f) => { buildPeer(f.display_name); api.chatThread(id).then(setThread).catch(() => {}); })
      .catch(() => buildPeer(`Игрок ${id}`));
  }, [vkId]);

  useEffect(() => {
    if (!peer) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const t = await api.chatThread(peer.vk_id);
        if (!cancelled) setThread(t);
      } catch { /* ignore */ }
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, [peer]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thread.length]);

  async function openPeer(c: Conversation) {
    setPeer(c);
    try {
      setThread(await api.chatThread(c.vk_id));
    } catch { /* ignore */ }
  }

  async function send() {
    if (!peer || !text.trim()) return;
    setBusy(true); setMsg(null);
    try {
      await api.sendChatMessage(peer.vk_id, text.trim());
      setText('');
      setThread(await api.chatThread(peer.vk_id));
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка отправки'));
    } finally { setBusy(false); }
  }

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>💬 Чат</h1>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {peer === null ? (
        convs.length === 0 ? (
          <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
            Переписки пока нет. Найдите игрока на странице «Фермы игроков» и напишите ему — его ID можно указать в чате.
          </div>
        ) : (
          <div className="fm-grid">
            {convs.map((c) => (
              <button key={c.vk_id} className="fm-card fm-rise" style={{ textAlign: 'left', cursor: 'pointer' }} onClick={() => openPeer(c)}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <strong style={{ flex: 1, fontSize: 15 }}>👤 {c.display_name}</strong>
                  {c.unread_count > 0 && (
                    <span style={{ background: '#e5484d', color: '#fff', borderRadius: 999, fontSize: 12, padding: '1px 8px' }}>{c.unread_count}</span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {c.last_message}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{fmt(c.last_message_at)}</div>
              </button>
            ))}
          </div>
        )
      ) : (
        <div>
          <button className="fm-btn fm-btn-outline fm-btn-sm" style={{ marginBottom: 8 }} onClick={() => { setPeer(null); setThread([]); openedPeerRef.current = null; nav('/chat'); api.chatConversations().then(setConvs).catch(() => {}); }}>
            ← К перепискам
          </button>
          <div className="fm-card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', fontSize: 15 }}>💬 {peer.display_name}</div>
            <div style={{ height: '52vh', overflowY: 'auto', padding: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {thread.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: 13, margin: 'auto' }}>Сообщений пока нет — напишите первым!</div>}
              {thread.map((m) => {
                const mine = m.from_user_id === user?.vk_id;
                return (
                  <div key={m.id} style={{ display: 'flex', justifyContent: mine ? 'flex-end' : 'flex-start' }}>
                    <div style={{
                      maxWidth: '78%',
                      padding: '8px 11px',
                      borderRadius: 12,
                      background: mine ? 'rgba(111,174,74,0.28)' : 'rgba(255,255,255,0.07)',
                      border: '1px solid rgba(255,255,255,0.08)',
                    }}>
                      <div style={{ fontSize: 14, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{m.text}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, textAlign: 'right' }}>{fmt(m.created_at)}</div>
                    </div>
                  </div>
                );
              })}
              <div ref={endRef} />
            </div>
            <div style={{ display: 'flex', gap: 8, padding: 10, borderTop: '1px solid var(--border)', flexWrap: 'wrap' }}>
              <input
                className="fm-input"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                placeholder="Сообщение…"
                style={{ flex: '1 1 200px', minWidth: 0 }}
              />
              <button className="fm-btn fm-btn-sm" style={{ flexShrink: 0 }} disabled={busy || !text.trim()} onClick={send}>➤ Отправить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
