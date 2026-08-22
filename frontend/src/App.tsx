import { lazy, Suspense, useEffect, type ReactNode, type ComponentType } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useVkBridge } from './context/VkBridgeContext';
import { useSession } from './context/SessionContext';
import Background from './components/Background';
import MiniAppShell from './components/MiniAppShell';
import { ConfirmHost } from './components/Confirm';
import { installGlobalErrorReporters } from './api/vkLogger';

function isStaleChunkError(err: unknown): boolean {
  const msg = String((err as Error)?.message || '');
  return (
    msg.includes('Failed to fetch dynamically imported module') ||
    msg.includes('Importing a module script failed')
  );
}

function reloadOnStaleChunk(err: unknown): Promise<{ default: React.ComponentType }> {
  try {
    if (!sessionStorage.getItem('farm_chunk_reload')) {
      sessionStorage.setItem('farm_chunk_reload', '1');
      window.location.reload();
    }
  } catch { /* ignore */ }
  return new Promise(() => {});
}

const lazyPage = (load: () => Promise<{ default: React.ComponentType }>) => {
  let retried = false;
  return lazy(() =>
    load().catch((err: unknown) => {
      if (!retried && isStaleChunkError(err)) {
        retried = true;
        return load();
      }
      if (isStaleChunkError(err)) {
        return reloadOnStaleChunk(err);
      }
      throw err;
    }),
  );
};

const OrdersPage = lazyPage(() => import('./pages/Orders'));
const OrderCatalogPage = lazyPage(() => import('./pages/OrderCatalog'));
const ProfilePage = lazyPage(() => import('./pages/Profile'));
const AdminPage = lazyPage(() => import('./pages/Admin'));
const FieldsPage = lazyPage(() => import('./pages/Fields'));
const FieldPage = lazyPage(() => import('./pages/Field'));
const MeadowPage = lazyPage(() => import('./pages/Meadow'));
const ShopPage = lazyPage(() => import('./pages/Shop'));
const InfirmaryPage = lazyPage(() => import('./pages/Infirmary'));
const InfirmaryScenePage = lazyPage(() => import('./pages/Infirmary').then((m) => ({ default: m.InfirmaryScenePage })));
const RemedyLabPage = lazyPage(() => import('./pages/RemedyLab'));
const CollectionPage = lazyPage(() => import('./pages/Collection'));
const InventoryPage = lazyPage(() => import('./pages/Inventory'));
const LibraryPage = lazyPage(() => import('./pages/Library'));
const BreweryHubPage = lazyPage(() => import('./pages/Brewery'));
const BreweryScenePage = lazyPage(() => import('./pages/Brewery').then((m) => ({ default: m.BreweryScenePage })));
const ForestBarHubPage = lazyPage(() => import('./pages/ForestBar'));
const ForestBarScenePage = lazyPage(() => import('./pages/ForestBar').then((m) => ({ default: m.ForestBarScenePage })));
const BonusesPage = lazyPage(() => import('./pages/Bonuses'));
const AchievementsPage = lazyPage(() => import('./pages/Achievements'));
const Onboarding = lazyPage(() => import('./pages/Onboarding'));
const PrehistoryPage = lazyPage(() => import('./pages/Prehistory').then((m) => ({ default: m.PrehistoryPage })));
const Prehistory = lazyPage(() => import('./pages/Prehistory')) as unknown as ComponentType<{ onDone?: () => void }>;
const DlcStoryGate = lazyPage(() =>
  import('./pages/Prehistory').then((m) => ({ default: m.DlcStoryGate as unknown as ComponentType })),
) as unknown as ComponentType<{ locationCode: string; name: string; emoji: string; children: ReactNode }>;
const LessonsPage = lazyPage(() => import('./pages/Lessons'));
const FarmsPage = lazyPage(() => import('./pages/Farms'));
const TradesPage = lazyPage(() => import('./pages/Trades'));
const ChatPage = lazyPage(() => import('./pages/Chat'));
const NotificationsPage = lazyPage(() => import('./pages/Notifications'));

const zoomed = { zoom: 'var(--app-scale)', width: 'calc(100% / var(--app-scale))', margin: '0 auto' } as const;

const LOCATION_TITLES: Record<string, string> = {
  infirmary: '🌲 Лечебница',
  brewery: '🧪 Зельеварение',
};

function LocationGate({ location, children }: { location: string; children: ReactNode }) {
  const { user } = useSession();
  const locked = user?.role !== 'admin' && (user?.locked_locations ?? []).includes(location);
  if (!locked) return <>{children}</>;
  return (
    <div style={zoomed}>
      <div style={{ maxWidth: 'calc(var(--shell-max-width) * 0.8)', margin: '0 auto', padding: 'var(--shell-pad)', textAlign: 'center' }}>
        <div className="fm-card fm-rise">
          <div style={{ fontSize: 46, marginBottom: 8 }}>🔒</div>
          <h1 style={{ fontSize: 22, lineHeight: 1.2 }}>
            {LOCATION_TITLES[location] ?? 'Локация'} пока закрыта
          </h1>
          <p style={{ color: 'var(--text-secondary)' }}>
            Это дополнение ещё не открыто.
          </p>
        </div>
      </div>
    </div>
  );
}

function Skeleton() {
  return (
    <div style={zoomed}>
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card" style={{ height: 120, opacity: 0.5 }}>Загрузка…</div>
      </div>
    </div>
  );
}

function StubPage() {
  return (
    <div style={zoomed}>
      <div style={{ maxWidth: 'calc(var(--shell-max-width) * 0.8)', margin: '0 auto', padding: 'var(--shell-pad)', textAlign: 'center' }}>
        <div className="fm-card fm-rise">
          <h1 style={{ fontSize: 'clamp(22px, 6vw, 30px)', lineHeight: 1.18, overflowWrap: 'anywhere' }}>
            История одной магической фермы
          </h1>
          <p style={{ color: 'var(--text-secondary)' }}>
            Скоро здесь расцветёт ваша волшебная ферма.
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>
            Мы готовим волшебство ✨
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>
            Игра будет доступна только для донов нашего междусобойчика
          </p>
        </div>
      </div>
    </div>
  );
}

function App() {
  const { vkUserId, loading } = useVkBridge();
  const { user, loading: sessionLoading, error: sessionError, refresh } = useSession();

  useEffect(() => { installGlobalErrorReporters(); }, []);

  useEffect(() => {
    try { sessionStorage.removeItem('farm_chunk_reload'); } catch { /* ignore */ }
  }, []);

  if (loading) return <><Background /><Skeleton /></>;
  if (vkUserId == null) return <><Background /><StubPage /></>;
  if (sessionLoading) return <><Background /><Skeleton /></>;
  if (!user) {
    const blocked = (sessionError ?? '').toLowerCase().includes('заблокирован');
    return (
      <>
        <Background />
        <div style={zoomed}>
          <div style={{ maxWidth: 'calc(var(--shell-max-width) * 0.8)', margin: '0 auto', padding: 'var(--shell-pad)', textAlign: 'center' }}>
            <div className="fm-card fm-rise">
              <div style={{ fontSize: 46, marginBottom: 8 }}>{blocked ? '🚫' : '✨'}</div>
              <h1 style={{ fontSize: 22, lineHeight: 1.2 }}>
                {blocked ? 'Аккаунт заблокирован' : 'История одной магической фермы'}
              </h1>
              <p style={{ color: 'var(--text-secondary)' }}>
                {blocked
                  ? 'Если вы считаете это ошибкой — свяжитесь с администратором игры.'
                  : 'Скоро здесь расцветёт ваша волшебная ферма.'}
              </p>
              {!blocked && <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Мы готовим волшебство ✨</p>}
            </div>
          </div>
        </div>
      </>
    );
  }
  if (user && user.role !== 'admin' && !user.story_seen) {
    return (
      <>
        <Background />
        <div style={zoomed}>
          <div style={{ maxWidth: 'calc(var(--shell-max-width) * 0.8)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
            <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>📜 Предыстория</h1>
            <Suspense fallback={<Skeleton />}><Prehistory onDone={() => refresh()} /></Suspense>
          </div>
        </div>
      </>
    );
  }
  if (user && user.role !== 'admin' && user.story_seen && !user.onboarding_done) {
    return (
      <>
        <Background />
        <div style={zoomed}>
          <Suspense fallback={<Skeleton />}><Onboarding /></Suspense>
        </div>
      </>
    );
  }

  return (
    <>
      <Background />
      <Suspense fallback={<Skeleton />}>
        <Routes>
          <Route path="/" element={<MiniAppShell><FieldsPage /></MiniAppShell>} />
          <Route path="/fields" element={<MiniAppShell><FieldsPage /></MiniAppShell>} />
          <Route path="/field/:id" element={<FieldPage />} />
          <Route path="/meadow/:id" element={<MeadowPage />} />
          <Route path="/shop/:id" element={<ShopPage />} />
          <Route path="/infirmary" element={<LocationGate location="infirmary"><DlcStoryGate locationCode="infirmary" name="Лесная лечебница" emoji="🌲"><MiniAppShell><InfirmaryPage /></MiniAppShell></DlcStoryGate></LocationGate>} />
          <Route path="/infirmary/:id" element={<LocationGate location="infirmary"><DlcStoryGate locationCode="infirmary" name="Лесная лечебница" emoji="🌲"><InfirmaryScenePage /></DlcStoryGate></LocationGate>} />
          <Route path="/remedy-lab/:id" element={<LocationGate location="infirmary"><RemedyLabPage /></LocationGate>} />
          <Route path="/meadow/:id" element={<LocationGate location="infirmary"><MeadowPage /></LocationGate>} />
          <Route path="/brewery" element={<LocationGate location="brewery"><DlcStoryGate locationCode="brewery" name="Зельеварение" emoji="🧪"><MiniAppShell><BreweryHubPage /></MiniAppShell></DlcStoryGate></LocationGate>} />
          <Route path="/brewery/:id" element={<LocationGate location="brewery"><DlcStoryGate locationCode="brewery" name="Зельеварение" emoji="🧪"><BreweryScenePage /></DlcStoryGate></LocationGate>} />
          <Route path="/forest-bar" element={<LocationGate location="infirmary"><MiniAppShell><ForestBarHubPage /></MiniAppShell></LocationGate>} />
          <Route path="/forest-bar/:id" element={<LocationGate location="infirmary"><ForestBarScenePage /></LocationGate>} />
          <Route path="/potions" element={<Navigate to="/brewery" replace />} />
          <Route path="/collection" element={<LocationGate location="infirmary"><MiniAppShell><CollectionPage /></MiniAppShell></LocationGate>} />
          <Route path="/inventory" element={<MiniAppShell><InventoryPage /></MiniAppShell>} />
          <Route path="/library" element={<MiniAppShell><LibraryPage /></MiniAppShell>} />
          <Route path="/bonuses" element={<LocationGate location="brewery"><MiniAppShell><BonusesPage /></MiniAppShell></LocationGate>} />
          <Route path="/achievements" element={<MiniAppShell><AchievementsPage /></MiniAppShell>} />
          <Route path="/story" element={<MiniAppShell><PrehistoryPage /></MiniAppShell>} />
          <Route path="/lessons" element={<MiniAppShell><LessonsPage /></MiniAppShell>} />
          <Route path="/farms" element={<MiniAppShell><FarmsPage /></MiniAppShell>} />
          <Route path="/trades" element={<MiniAppShell><TradesPage /></MiniAppShell>} />
          <Route path="/chat" element={<MiniAppShell><ChatPage /></MiniAppShell>} />
          <Route path="/chat/:vkId" element={<MiniAppShell><ChatPage /></MiniAppShell>} />
          <Route path="/notifications" element={<MiniAppShell><NotificationsPage /></MiniAppShell>} />
          <Route path="/orders" element={<MiniAppShell><OrdersPage /></MiniAppShell>} />
          <Route path="/orders/catalog" element={<MiniAppShell><OrderCatalogPage /></MiniAppShell>} />
          <Route path="/profile" element={<MiniAppShell><ProfilePage /></MiniAppShell>} />
          <Route path="/admin" element={<MiniAppShell><AdminPage /></MiniAppShell>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      <ConfirmHost />
    </>
  );
}

export default App;
