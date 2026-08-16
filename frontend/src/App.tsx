import { lazy, Suspense, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useVkBridge } from './context/VkBridgeContext';
import { useSession } from './context/SessionContext';
import Background from './components/Background';
import MiniAppShell from './components/MiniAppShell';
import { isAdminAllowed } from './auth/adminGate';
import { installGlobalErrorReporters } from './api/vkLogger';

function reloadOnStaleChunk(err: unknown): never {
  const msg = String((err as Error)?.message || '');
  if (msg.includes('Failed to fetch dynamically imported module')) {
    try {
      if (!sessionStorage.getItem('farm_chunk_reload')) {
        sessionStorage.setItem('farm_chunk_reload', '1');
        window.location.reload();
      }
    } catch { /* ignore */ }
  }
  throw err;
}

const lazyPage = (load: () => Promise<{ default: React.ComponentType }>) =>
  lazy(() => load().catch(reloadOnStaleChunk));

const OrdersPage = lazyPage(() => import('./pages/Orders'));
const OrderCatalogPage = lazyPage(() => import('./pages/OrderCatalog'));
const ProfilePage = lazyPage(() => import('./pages/Profile'));
const AdminPage = lazyPage(() => import('./pages/Admin'));
const FieldsPage = lazyPage(() => import('./pages/Fields'));
const FieldPage = lazyPage(() => import('./pages/Field'));
const InventoryPage = lazyPage(() => import('./pages/Inventory'));
const LibraryPage = lazyPage(() => import('./pages/Library'));
const BarnyardPage = lazyPage(() => import('./pages/Barnyard'));
const PetsPage = lazyPage(() => import('./pages/PetsPage'));
const PotionsPage = lazyPage(() => import('./pages/PotionsPage'));
const AchievementsPage = lazyPage(() => import('./pages/Achievements'));
const Onboarding = lazyPage(() => import('./pages/Onboarding'));

const zoomed = { zoom: 'var(--app-scale)', width: 'calc(100% / var(--app-scale))', margin: '0 auto' } as const;

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
        </div>
      </div>
    </div>
  );
}

function App() {
  const { vkUserId, loading } = useVkBridge();
  const { user, loading: sessionLoading } = useSession();

  useEffect(() => { installGlobalErrorReporters(); }, []);

  useEffect(() => {
    try { sessionStorage.removeItem('farm_chunk_reload'); } catch { /* ignore */ }
  }, []);

  if (loading) return <><Background /><Skeleton /></>;
  if (!isAdminAllowed(vkUserId)) return <><Background /><StubPage /></>;
  if (sessionLoading) return <><Background /><Skeleton /></>;
  if (!user) return <><Background /><StubPage /></>;
  if (user && !user.onboarding_done) {
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
          <Route path="/inventory" element={<MiniAppShell><InventoryPage /></MiniAppShell>} />
          <Route path="/library" element={<MiniAppShell><LibraryPage /></MiniAppShell>} />
          <Route path="/barnyard" element={<MiniAppShell><BarnyardPage /></MiniAppShell>} />
          <Route path="/pets" element={<MiniAppShell><PetsPage /></MiniAppShell>} />
          <Route path="/potions" element={<MiniAppShell><PotionsPage /></MiniAppShell>} />
          <Route path="/achievements" element={<MiniAppShell><AchievementsPage /></MiniAppShell>} />
          <Route path="/orders" element={<MiniAppShell><OrdersPage /></MiniAppShell>} />
          <Route path="/orders/catalog" element={<MiniAppShell><OrderCatalogPage /></MiniAppShell>} />
          <Route path="/profile" element={<MiniAppShell><ProfilePage /></MiniAppShell>} />
          <Route path="/admin" element={<MiniAppShell><AdminPage /></MiniAppShell>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </>
  );
}

export default App;
