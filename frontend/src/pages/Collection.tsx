import { useEffect, useState } from 'react';
import { api, type Collection } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';

const LEVEL_LABEL: Record<number, string> = { 1: 'Уровень 1', 2: 'Уровень 2', 3: 'Уровень 3' };

export default function CollectionPage() {
  const [collection, setCollection] = useState<Collection | null>(null);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.collection()
      .then(setCollection)
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="fm-card">Загрузка коллекции…</div>
    );
  }

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ fontSize: 20 }}>🃏 Коллекция карточек</h1>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {collection?.levels.map((lvl) => (
        <div key={lvl.level} style={{ marginBottom: 16 }}>
          <h3 style={{ margin: '0 0 8px' }}>
            {LEVEL_LABEL[lvl.level] || `Уровень ${lvl.level}`}
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}> ({lvl.earned_count}/{lvl.total_count})</span>
          </h3>
          <div className="fm-grid">
            {lvl.cards.map((c) => (
              <div key={c.patient_id} className="fm-card fm-rise" style={{ textAlign: 'center' }}>
                {c.earned && c.card_image_url ? (
                  <img src={mediaUrl(c.card_image_url)} alt={c.patient_name} style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 8 }} />
                ) : (
                  <div style={{ width: 80, height: 80, borderRadius: 8, background: '#1a2414', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 36, margin: '0 auto' }}>
                    👤
                  </div>
                )}
                <div style={{ fontSize: 13, marginTop: 6 }}>{c.earned ? c.patient_name : '???'}</div>
                {!c.earned && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>не вылечен</div>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
