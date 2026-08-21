import { useState, type ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSession } from '../context/SessionContext';

interface Tab {
  path: string;
  label: string;
  location?: string;
  locked?: boolean;
  hideWhenLocked?: boolean;
}

interface Props {
  children: ReactNode;
}

const BAR_BG = 'linear-gradient(180deg, rgba(10,16,8,0.92) 0%, rgba(10,16,8,0.78) 100%)';

const BASE_TABS: Tab[] = [
  { path: '/', label: '🗺️ Поля' },
  { path: '/infirmary', label: '🌲 Лечебница', location: 'infirmary' },
  { path: '/library', label: '📖 Библиотека' },
  { path: '/story', label: '📜 Предыстория' },
  { path: '/lessons', label: '🎬 Уроки' },
  { path: '/brewery', label: '🧪 Зельеварение', location: 'brewery' },
  { path: '/bonuses', label: '⚡ Бонусы', location: 'brewery', hideWhenLocked: true },
  { path: '/inventory', label: '📦 Склад' },
  { path: '/farms', label: '🌾 Фермы игроков' },
  { path: '/orders', label: '🧺 Заказы' },
  { path: '/achievements', label: '🏆 Достижения' },
  { path: '/collection', label: '🃏 Коллекция', location: 'infirmary', hideWhenLocked: true },
  { path: '/profile', label: '👤 Профиль' },
];

function MiniAppShell({ children }: Props) {
  const nav = useNavigate();
  const loc = useLocation();
  const { user } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);

  const isLocked = (code?: string) =>
    user?.role !== 'admin' && !!code && (user?.locked_locations ?? []).includes(code);

  const tabs: Tab[] = BASE_TABS
    .filter((t) => !(t.hideWhenLocked && isLocked(t.location)))
    .map((t) => (isLocked(t.location) ? { ...t, label: `${t.label} 🔒`, locked: true } : t));
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
                onClick={() => (t.locked ? undefined : go(t.path))}
                disabled={t.locked}
                className={active?.path === t.path && !t.locked ? 'fm-btn' : 'fm-btn fm-btn-outline'}
                style={{
                  padding: '16px 18px',
                  fontSize: 17,
                  ...(t.locked ? { opacity: 0.55, cursor: 'not-allowed' } : {}),
                }}
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
        }}
      >
        {children}
      </div>
    </>
  );
}

export default MiniAppShell;
