import { useEffect, useState } from 'react';
import { api, type Collection } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';

const LEVEL_LABEL: Record<number, string> = { 1: 'Уровень 1', 2: 'Уровень 2', 3: 'Уровень 3' };

export default function CollectionPage() {
  const [collection, setCollection] = useState<Collection | null>(null);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [zoomed, setZoomed] = useState<{ url: string; name: string } | null>(null);

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

  const levels = collection?.levels ?? [];
  const totalEarned = levels.reduce((s, l) => s + l.earned_count, 0);
  const totalCards = levels.reduce((s, l) => s + l.total_count, 0);

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
      <h1 style={{ fontSize: 20 }}>🃏 Коллекция карточек</h1>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 14px' }}>
        Здесь собираются карточки вылеченных животных. Вылечите и выпустите на волю животное в 🌲 Лесной лечебнице — и его карточка откроется в этой коллекции.
      </p>
      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {totalCards === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
          Коллекция пуста — животные появятся в 🌲 Лесной лечебнице. Вылечите их, чтобы получить карточки.
        </div>
      ) : totalEarned === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)', marginBottom: 14 }}>
          В коллекции пока пусто. Вылечите животное в 🌲 Лесной лечебнице — его карточка откроется здесь.
        </div>
      ) : null}

      {levels.map((lvl) => {
        if (lvl.total_count === 0) return null;
        return (
          <div key={lvl.level} style={{ marginBottom: 16 }}>
            <h3 style={{ margin: '0 0 8px' }}>
              {LEVEL_LABEL[lvl.level] || `Уровень ${lvl.level}`}
              <span style={{ color: 'var(--text-muted)', fontSize: 13 }}> ({lvl.earned_count}/{lvl.total_count})</span>
            </h3>
            <div className="fm-grid">
              {lvl.cards.map((c) =>
                c.earned ? (
                  <div
                    key={c.patient_id}
                    className="fm-card fm-rise"
                    style={{ textAlign: 'center', cursor: c.card_image_url ? 'zoom-in' : 'default' }}
                    onClick={() => { if (c.card_image_url) setZoomed({ url: mediaUrl(c.card_image_url), name: c.patient_name }); }}
                  >
                    {c.card_image_url ? (
                      <img src={mediaUrl(c.card_image_url)} alt={c.patient_name} style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 8 }} />
                    ) : (
                      <div style={{ width: 80, height: 80, borderRadius: 8, background: '#1a2414', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 36, margin: '0 auto' }}>
                        👤
                      </div>
                    )}
                    <div style={{ fontSize: 13, marginTop: 6 }}>{c.patient_name}</div>
                  </div>
                ) : (
                  <div key={c.patient_id} className="fm-card" style={{ textAlign: 'center', opacity: 0.55 }}>
                    <div style={{ width: 80, height: 80, borderRadius: 8, background: '#1a2414', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 36, margin: '0 auto' }}>
                      🔒
                    </div>
                    <div style={{ fontSize: 13, marginTop: 6 }}>{c.patient_name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Откроется в Лесной лечебнице</div>
                  </div>
                ),
              )}
            </div>
          </div>
        );
      })}

      {zoomed && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.7)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 16 }}
          onClick={() => setZoomed(null)}
        >
          <img src={zoomed.url} alt={zoomed.name} style={{ maxWidth: '90vw', maxHeight: '80vh', borderRadius: 12, objectFit: 'contain' }} />
          <div style={{ color: '#fff', marginTop: 10, fontSize: 14 }}>{zoomed.name}</div>
        </div>
      )}
    </div>
  );
}
