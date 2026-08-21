import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api } from '../api/endpoints';

interface Tab {
  path: string;
  label: string;
  location?: string;
  locked?: boolean;
  hideWhenLocked?: boolean;
  unread?: number;
  section?: string;
}

interface Props {
  children: ReactNode;
}

const BAR_BG = 'linear-gradient(180deg, rgba(10,16,8,0.92) 0%, rgba(10,16,8,0.78) 100%)';

const BASE_TABS: Tab[] = [
  { path: '/', label: '🗺️ Поля' },
  { path: '/infirmary', label: '🌲 Лечебница', location: 'infirmary' },
  { path: '/library', label: '📖 Библиотека' },
  { path: '/brewery', label: '🧪 Зельеварение', location: 'brewery' },
  { path: '/bonuses', label: '⚡ Бонусы', location: 'brewery', hideWhenLocked: true },
  { path: '/inventory', label: '📦 Склад' },
  { path: '/orders', label: '🧺 Заказы' },
  { path: '/achievements', label: '🏆 Достижения' },
  { path: '/collection', label: '🃏 Коллекция', location: 'infirmary', hideWhenLocked: true },
  { path: '/profile', label: '👤 Профиль', section: 'profile' },
  { path: '/lessons', label: '🎬 Уроки', section: 'profile' },
  { path: '/trades', label: '🤝 Бартер', section: 'profile' },
  { path: '/chat', label: '💬 Чат', section: 'profile' },
  { path: '/farms', label: '🌾 Фермы игроков', section: 'profile' },
];

function MiniAppShell({ children }: Props) {
  const nav = useNavigate();
  const loc = useLocation();
  const { user } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);
  const [chatUnread, setChatUnread] = useState(0);
  const [notifUnread, setNotifUnread] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const convs = await api.chatConversations();
        if (!cancelled) setChatUnread(convs.reduce((s, c) => s + (c.unread_count || 0), 0));
      } catch { /* ignore */ }
      try {
        const n = await api.notificationUnreadCount();
        if (!cancelled) setNotifUnread(n.count);
      } catch { /* ignore */ }
    };
    tick();
    const id = setInterval(tick, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const isLocked = (code?: string) =>
    user?.role !== 'admin' && !!code && (user?.locked_locations ?? []).includes(code);

  const tabs: Tab[] = BASE_TABS
    .filter((t) => !(t.hideWhenLocked && isLocked(t.location)))
    .map((t) => {
      const locked = isLocked(t.location);
      const tab: Tab = locked ? { ...t, label: `${t.label} 🔒`, locked: true } : { ...t };
      if (t.path === '/chat' && chatUnread > 0) tab.unread = chatUnread;
      return tab;
    });
  if (user?.role === 'admin') tabs.push({ path: '/admin', label: '⚙️ Управление' });

  const active = tabs.find(
    (t) => loc.pathname === t.path || (t.path !== '/' && loc.pathname.startsWith(t.path)),
  );

  function go(path: string) {
    setMenuOpen(false);
    nav(path);
  }

  return (
    <>
      {user?.status === 'readonly' && (
        <div
          style={{
            background: 'rgba(120,80,10,0.92)',
            color: '#ffe9b0',
            fontSize: 13,
            textAlign: 'center',
            padding: '6px 12px',
          }}
        >
          👁 Режим только просмотра — действия недоступны
        </div>
      )}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '6px 12px',
          paddingTop: '6px',
          position: 'sticky',
          top: 0,
          zIndex: 20,
          background: BAR_BG,
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          borderBottom: '1px solid rgba(0,0,0,0.3)',
        }}
      >
        <button
          onClick={() => setMenuOpen(true)}
          className="fm-btn fm-btn-outline"
          aria-label="Меню"
          style={{
            padding: '8px 12px',
            fontSize: 16,
            background: 'rgba(255,255,255,0.14)',
            color: '#ffffff',
            borderColor: 'rgba(255,255,255,0.25)',
          }}
        >
          ☰
        </button>
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 17,
            fontWeight: 600,
            color: '#ffffff',
            textShadow: '0 1px 3px rgba(0,0,0,0.7)',
            flex: 1,
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {active?.label ?? '🗺️ Поля'}
        </span>
        {active?.unread ? (
          <span style={{ flexShrink: 0, background: '#e5484d', color: '#fff', borderRadius: 999, fontSize: 13, padding: '2px 9px', fontWeight: 700 }}>{active.unread}</span>
        ) : null}
        <button
          onClick={() => nav('/notifications')}
          className="fm-btn fm-btn-outline"
          aria-label="Уведомления"
          style={{
            position: 'relative',
            flexShrink: 0,
            padding: '8px 12px',
            fontSize: 16,
            background: 'rgba(255,255,255,0.14)',
            color: '#ffffff',
            borderColor: 'rgba(255,255,255,0.25)',
          }}
        >
          🔔
          {notifUnread > 0 && (
            <span style={{ position: 'absolute', top: -4, right: -4, background: '#e5484d', color: '#fff', borderRadius: 999, fontSize: 12, padding: '1px 7px', fontWeight: 700, minWidth: 20, textAlign: 'center' }}>
              {notifUnread}
            </span>
          )}
        </button>
      </div>

      {menuOpen && (
        <div
          onClick={() => setMenuOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 50,
            background: 'rgba(10,14,8,0.88)',
            backdropFilter: 'blur(4px)',
            WebkitBackdropFilter: 'blur(4px)',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            padding: 'calc(20px + var(--vk-inset-top, 0px)) 20px 20px',
          }}
        >
          <button
            onClick={() => setMenuOpen(false)}
            className="fm-btn"
            style={{ alignSelf: 'flex-end', padding: '8px 16px', fontSize: 16 }}
            aria-label="Закрыть"
          >
            ✕
          </button>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
              width: '100%',
              maxWidth: 'calc(var(--shell-max-width) * 0.767)',
              marginTop: 16,
            }}
          >
            {tabs.map((t, idx) => {
              const prevSection = idx > 0 ? tabs[idx - 1].section : undefined;
              const showHeader = !!t.section && t.section !== prevSection;
              return (
                <div key={t.path} style={{ display: 'contents' }}>
                  {showHeader && (
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginTop: idx > 0 ? 12 : 0, textAlign: 'center' }}>
                      {t.section === 'profile' ? '👤 Профиль' : t.section}
                    </div>
                  )}
                  <button
                    onClick={() => (t.locked ? undefined : go(t.path))}
                    disabled={t.locked}
                    className={active?.path === t.path && !t.locked ? 'fm-btn' : 'fm-btn fm-btn-outline'}
                    style={{
                      padding: '16px 18px',
                      fontSize: 17,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      justifyContent: 'space-between',
                      ...(t.locked ? { opacity: 0.55, cursor: 'not-allowed' } : {}),
                    }}
                  >
                    <span>{t.label}</span>
                    {t.unread ? (
                      <span style={{ flexShrink: 0, background: '#e5484d', color: '#fff', borderRadius: 999, fontSize: 13, padding: '2px 9px', fontWeight: 700 }}>{t.unread}</span>
                    ) : null}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div
        style={{
          zoom: 'var(--app-scale)',
          width: 'calc(100% / var(--app-scale))',
          margin: '0 auto',
        }}
      >
        {children}
      </div>
    </>
  );
}

export default MiniAppShell;
