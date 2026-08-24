import { useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import SubscriptionBox from '../components/SubscriptionBox';

export default function Paywall({ onWatch }: { onWatch?: () => void }) {
  const nav = useNavigate();
  const { user } = useSession();

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'calc(16px + var(--vk-inset-top, 0px)) 6px 32px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 44 }}>⏳</div>
        <h1 style={{ fontSize: 22, margin: '8px 0 0' }}>
          {user?.trial_until ? 'Пробный период закончился' : 'Нужна подписка'}
        </h1>
      </div>
      <div className="fm-story-text" style={{ textAlign: 'center' }}>
        Чтобы продолжить играть, оформите подписку. Просмотр игры остаётся бесплатным.
      </div>
      <SubscriptionBox onPaid={() => nav('/')} />
      <button
        className="fm-btn fm-btn-outline"
        onClick={() => (onWatch ? onWatch() : nav('/'))}
        style={{ padding: '12px 16px' }}
      >
        👁 Смотреть игру (только просмотр)
      </button>
    </div>
  );
}
