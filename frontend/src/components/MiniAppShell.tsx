import { useState, type ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSession } from '../context/SessionContext';

interface Tab {
  path: string;
  label: string;
}

interface Props {
  children: ReactNode;
}

const BAR_BG = 'linear-gradient(180deg, rgba(10,16,8,0.92) 0%, rgba(10,16,8,0.78) 100%)';

const BASE_TABS: Tab[] = [
  { path: '/', label: '🗺️ Поля' },
  { path: '/library', label: '📖 Библиотека' },
  { path: '/barnyard', label: '🐄 Скотный двор' },
  { path: '/pets', label: '🐾 Питомцы' },
  { path: '/potions', label: '🧪 Зелья' },
  { path: '/inventory', label: '📦 Склад' },
  { path: '/orders', label: '🧺 Заказы' },
  { path: '/achievements', label: '🏆 Достижения' },
  { path: '/profile', label: '👤 Профиль' },
];

function MiniAppShell({ children }: Props) {
  const nav = useNavigate();
  const loc = useLocation();
  const { user } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);

  const tabs: Tab[] = [...BASE_TABS];
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
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '6px 12px',
          paddingTop: 'calc(6px + var(--vk-inset-top, 0px))',
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
            {tabs.map((t) => (
              <button
                key={t.path}
                onClick={() => go(t.path)}
                className={active?.path === t.path ? 'fm-btn' : 'fm-btn fm-btn-outline'}
                style={{ padding: '16px 18px', fontSize: 17 }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div
        style={{
          zoom: 'var(--app-scale)',
          width: 'calc(100% / var(--app-scale))',
          margin: '0 auto',
          paddingTop: 'calc(50px + var(--vk-inset-top, 0px))',
        }}
      >
        {children}
      </div>
    </>
  );
}

export default MiniAppShell;
