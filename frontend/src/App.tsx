import { Routes, Route, Navigate } from 'react-router-dom';
import { useVkBridge } from './context/VkBridgeContext';
import { useSession } from './context/SessionContext';
import Background from './components/Background';
import MiniAppShell from './components/MiniAppShell';
import OrdersPage from './pages/Orders';
import ProfilePage from './pages/Profile';
import AdminPage from './pages/Admin';
import FieldsPage from './pages/Fields';
import FieldPage from './pages/Field';
import InventoryPage from './pages/Inventory';
import LibraryPage from './pages/Library';
import BarnyardPage from './pages/Barnyard';
import PetsPage from './pages/PetsPage';
import PotionsPage from './pages/PotionsPage';
import Onboarding from './pages/Onboarding';
import { hasBetaList, isBetaAllowed } from './auth/betaGate';

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
        <Onboarding />
      </>
    );
  }

  return (
    <>
      <Background />
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
    </>
  );
}

export default App;
