import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useVkBridge } from './context/VkBridgeContext';
import { useSession } from './context/SessionContext';
import Background from './components/Background';
import MiniAppShell from './components/MiniAppShell';
import { hasBetaList, isBetaAllowed } from './auth/betaGate';

const OrdersPage = lazy(() => import('./pages/Orders'));
const ProfilePage = lazy(() => import('./pages/Profile'));
const AdminPage = lazy(() => import('./pages/Admin'));
const FieldsPage = lazy(() => import('./pages/Fields'));
const FieldPage = lazy(() => import('./pages/Field'));
const InventoryPage = lazy(() => import('./pages/Inventory'));
const LibraryPage = lazy(() => import('./pages/Library'));
const BarnyardPage = lazy(() => import('./pages/Barnyard'));
const PetsPage = lazy(() => import('./pages/PetsPage'));
const PotionsPage = lazy(() => import('./pages/PotionsPage'));
const Onboarding = lazy(() => import('./pages/Onboarding'));

function Skeleton() {
  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <div className="fm-card" style={{ height: 120, opacity: 0.5 }}>Загрузка…</div>
    </div>
  );
}

function BetaDenied() {
  return (
    <div style={{ maxWidth: 480, margin: '0 auto', padding: 'var(--shell-pad)', textAlign: 'center' }}>
      <div className="fm-card fm-rise">
        <h1>🌾 Ферма</h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Игра пока на закрытом тестировании. Доступ открывается постепенно.
        </p>
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>
          Скоро здесь расцветёт ваша волшебная ферма ✨
        </p>
      </div>
    </div>
  );
}

function App() {
  const { vkUserId, loading } = useVkBridge();
  const { user, loading: sessionLoading } = useSession();

  if (loading) return <><Background /><Skeleton /></>;
  if (hasBetaList() && !isBetaAllowed(vkUserId)) return <><Background /><BetaDenied /></>;
  if (sessionLoading) return <><Background /><Skeleton /></>;
  if (user && !user.onboarding_done) {
    return (
      <>
        <Background />
        <Suspense fallback={<Skeleton />}><Onboarding /></Suspense>
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
          <Route path="/orders" element={<MiniAppShell><OrdersPage /></MiniAppShell>} />
          <Route path="/profile" element={<MiniAppShell><ProfilePage /></MiniAppShell>} />
          <Route path="/admin" element={<MiniAppShell><AdminPage /></MiniAppShell>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </>
  );
}

export default App;
