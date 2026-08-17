import { useCallback, useEffect, useState } from 'react';
import { useSession } from '../context/SessionContext';
import { api, type Animal, type BarnyardPen, type BarnyardProduceResult, type CrystalCard } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import Toast from '../components/Toast';
import StitchReportForm from '../components/StitchReportForm';

const DICE_FACES = ['', '⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];

export default function BarnyardPage() {
  const { refresh, loading: sessionLoading } = useSession();
  const [pens, setPens] = useState<BarnyardPen[]>([]);
  const [animals, setAnimals] = useState<Animal[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [installPen, setInstallPen] = useState<BarnyardPen | null>(null);
  const [installAnimalId, setInstallAnimalId] = useState<number | null>(null);

  const [produceResult, setProduceResult] = useState<BarnyardProduceResult | null>(null);
  const [showDiceVideo, setShowDiceVideo] = useState(false);
  const [diceVideoUrl, setDiceVideoUrl] = useState<string | null>(null);
  const [diceFaces, setDiceFaces] = useState<(string | null)[]>([null, null, null, null, null, null, null]);
  const [crystalCards, setCrystalCards] = useState<CrystalCard[]>([]);

  const [cardResult, setCardResult] = useState<{ cards: { color: string; value: number; is_treasure: boolean }[]; title: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, a] = await Promise.all([api.barnyardPens(), api.animalsAvailable()]);
      setPens(p);
      setAnimals(a);
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    Promise.all([
      api.gameMediaByCode('dice_roll').then(gm => gm.url ? mediaUrl(gm.url) : null).catch(() => null),
      ...([1, 2, 3, 4, 5, 6].map(i =>
        api.gameMediaByCode(`dice_face_${i}`).then(gm => gm.url ? mediaUrl(gm.url) : null).catch(() => null)
      )),
      api.crystalCards().catch(() => [] as CrystalCard[]),
    ]).then(([video, ...results]) => {
      const faces = results.slice(0, 6) as (string | null)[];
      const cards = results[6] as CrystalCard[];
      setDiceVideoUrl(video);
      setDiceFaces([null, ...faces]);
      if (cards) setCrystalCards(cards);
    });
  }, []);

  useEffect(() => { if (!sessionLoading) load(); }, [load, sessionLoading]);

  async function doInstall() {
    if (!installPen || installAnimalId == null) return;
    setBusy(true); setMsg(null);
    try {
      const res = await api.barnyardInstall(installPen.id, installAnimalId);
      const animal = animals.find(a => a.id === installAnimalId);
      let cards: { color: string; value: number; is_treasure: boolean }[] = [];
      if (res.drawn_cards_json) {
        try { cards = JSON.parse(res.drawn_cards_json); } catch {}
      }
      if (cards.length > 0) {
        setCardResult({ cards, title: `🏗 ${animal?.name || 'Загон'} — карты` });
      } else {
        setMsg('✓ Загон строится!');
      }
      setInstallPen(null); setInstallAnimalId(null);
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doProduce(pen: BarnyardPen) {
    setBusy(true); setMsg(null);
    try {
      const result = await api.barnyardProduce(pen.id);
      setShowDiceVideo(!!diceVideoUrl);
      setProduceResult(result);
      await load(); await refresh();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  if (loading) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка скотного двора…</div>
      </div>
    );
  }

  const sorted = [...pens].sort((a, b) => (a.opening_order ?? 9999) - (b.opening_order ?? 9999));

  return (
    <>
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

        {sorted.length === 0 ? (
          <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
            Загоны пока не открыты. Они появляются с повышением уровня (прокачка «Животноводство»).
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 10 }}>
            {sorted.map((pen) => (
              <div key={pen.id} className="fm-card fm-rise" style={{ textAlign: 'center' }}>
                {pen.status === 'empty' && (
                  <>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                      Свободное место
                    </div>
                    <div style={{ fontSize: 40, lineHeight: 1, marginBottom: 8, opacity: 0.7 }}>🏚️</div>
                    <button
                      className="fm-btn fm-btn-outline"
                      style={{ width: '100%' }}
                      disabled={busy || animals.length === 0}
                      onClick={() => {
                        setInstallPen(pen);
                        setInstallAnimalId(animals[0]?.id ?? null);
                      }}
                    >
                      🏗 Построить загон
                    </button>
                  </>
                )}

                {pen.status === 'building' && (
                  <>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                      Загон #{pen.opening_order} · строится
                    </div>
                    {pen.image_empty_pen_url ? (
                      <img
                        src={mediaUrl(pen.image_empty_pen_url)}
                        alt=""
                        style={{ width: '100%', height: 110, objectFit: 'contain', marginBottom: 6 }}
                      />
                    ) : (
                      <div style={{ fontSize: 40, lineHeight: 1, marginBottom: 6, opacity: 0.7 }}>🏚️</div>
                    )}
                    <div style={{ color: 'var(--text-muted)', marginBottom: 8, fontSize: 13 }}>
                      Пустой загон — вышейте норму, чтобы заселить животное
                    </div>
                    <div className="fm-progress" style={{ marginBottom: 6 }}>
                      <div
                        className="fm-progress-fill"
                        style={{
                          width: `${pen.required > 0 ? Math.min(100, Math.round((pen.accumulated / pen.required) * 100)) : 0}%`,
                        }}
                      />
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
                      {pen.accumulated}/{pen.required} ❎
                    </div>
                    <StitchReportForm
                      contextType="animal_build"
                      contextId={pen.id}
                      required={Math.max(0, pen.required - pen.accumulated)}
                      busy={busy}
                      buttonText="Заселить животное"
                      onDone={async () => { setMsg('✓ Животное в загоне!'); await load(); await refresh(); }}
                    />
                  </>
                )}

                {pen.status === 'ready' && pen.last_die == null && (
                  <>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                      Загон #{pen.opening_order}
                    </div>
                    {pen.image_pen_url ? (
                      <img
                        src={mediaUrl(pen.image_pen_url)}
                        alt=""
                        style={{ width: '100%', height: 110, objectFit: 'contain', marginBottom: 6 }}
                      />
                    ) : (
                      <div style={{ fontSize: 40, lineHeight: 1, marginBottom: 4 }}>
                        {pen.animal_emoji || '🐾'}
                      </div>
                    )}
                    <div style={{ fontWeight: 600, marginBottom: 10 }}>{pen.animal_name}</div>
                    <button
                      className="fm-btn"
                      style={{ width: '100%' }}
                      disabled={busy}
                      onClick={() => doProduce(pen)}
                    >
                      🥚 Получить продукцию
                    </button>
                  </>
                )}

                {pen.status === 'ready' && pen.last_die != null && (
                  <>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                      Загон #{pen.opening_order} · производство
                    </div>
                    {pen.image_harvested_url || pen.image_pen_url ? (
                      <img
                        src={mediaUrl((pen.image_harvested_url || pen.image_pen_url)!)}
                        alt=""
                        style={{ width: '100%', height: 110, objectFit: 'contain', marginBottom: 6 }}
                      />
                    ) : (
                      <div style={{ fontSize: 40, lineHeight: 1, marginBottom: 4 }}>
                        {pen.animal_emoji || '🐾'}
                      </div>
                    )}
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>{pen.animal_name}</div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
                      Норма продукции: {pen.required} ❎
                    </div>
                    <StitchReportForm
                      contextType="animal_produce"
                      contextId={pen.id}
                      required={pen.required}
                      busy={busy}
                      buttonText="Получить продукцию на склад"
                      onDone={async () => { setMsg('✓ Продукция на складе!'); await load(); await refresh(); }}
                    />
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Модалка постройки загона */}
      {installPen && (
        <Modal title="🏗 Построить загон" onClose={() => setInstallPen(null)}>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 10 }}>
            Выберите животное — загон появится на поле пустым,
            а животное заселится после зачёта вышивки.
          </p>
          {animals.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Каталог животных пуст.</div>
          ) : (
            <select className="fm-input" value={installAnimalId ?? ''} onChange={(e) => setInstallAnimalId(Number(e.target.value))}>
              {animals.map((a) => (
                <option key={a.id} value={a.id}>{a.emoji} {a.name}</option>
              ))}
            </select>
          )}
          <button
            className="fm-btn"
            style={{ width: '100%', marginTop: 14 }}
            disabled={busy || installAnimalId == null}
            onClick={doInstall}
          >
            Построить
          </button>
        </Modal>
      )}

      {/* Модалка результата продукции */}
      {produceResult && (
        <Modal title="🎲 Результат броска" onClose={() => { setProduceResult(null); setShowDiceVideo(false); }} wide={showDiceVideo}>
          {showDiceVideo && diceVideoUrl ? (
            <div style={{ textAlign: 'center' }}>
              <video
                src={diceVideoUrl}
                autoPlay
                muted
                playsInline
                style={{ width: '100%', maxHeight: '50vh', borderRadius: 8, marginBottom: 8 }}
                onEnded={() => setShowDiceVideo(false)}
                onError={() => setShowDiceVideo(false)}
              />
              <button className="fm-btn fm-btn-sm fm-btn-outline" onClick={() => setShowDiceVideo(false)}>
                Пропустить
              </button>
            </div>
          ) : (
            <div style={{ textAlign: 'center' }}>
              {diceFaces[produceResult.die] ? (
                <img src={diceFaces[produceResult.die]!} alt="" style={{ width: '30vw', maxWidth: 200, height: 'auto', marginBottom: 10 }} />
              ) : (
                <div style={{ fontSize: 48, lineHeight: 1, marginBottom: 10 }}>
                  {DICE_FACES[produceResult.die] || produceResult.die}
                </div>
              )}
              <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 4 }}>
                {produceResult.animal_name}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 10 }}>
                Норма вышивки: {produceResult.required} ❎
              </div>
              <div className="fm-chip" style={{ display: 'inline-block', fontSize: 16 }}>
                +{produceResult.product_coins} 🪙
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12 }}>
                Вышейте норму и отчитайтесь в карточке загона — продукция придёт на склад.
              </p>
            </div>
          )}
        </Modal>
      )}

      {/* Модалка карт кристаллов */}
      {cardResult && (
        <Modal title={cardResult.title} onClose={() => setCardResult(null)}>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
            {cardResult.cards.map((c, i) => {
              const cardImg = crystalCards.find(
                cc => cc.color === c.color && cc.value === c.value && cc.is_treasure === c.is_treasure
              )?.image_url;
              return (
                <div key={i} style={{ textAlign: 'center', padding: 6, borderRadius: 10, background: 'var(--bg-secondary)', border: '1px solid var(--border)', minWidth: 100 }}>
                  {cardImg ? (
                    <img src={mediaUrl(cardImg)} alt="" style={{ width: '30vw', maxWidth: 160, height: 'auto', objectFit: 'contain', marginBottom: 4 }} />
                  ) : (
                    <div style={{ fontSize: 36, lineHeight: 1, marginBottom: 4 }}>
                      {c.is_treasure ? '💎' : c.color === 'green' ? '🟢' : c.color === 'blue' ? '🔵' : '🟣'}
                    </div>
                  )}
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {c.is_treasure ? 'Сокровище' : `${c.value}`}
                  </div>
                </div>
              );
            })}
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
            Вышейте норму по картам — и в загоне появится животное.
          </p>
        </Modal>
      )}
    </>
  );
}

function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean }) {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: wide ? 8 : 16 }}>
      <div className="fm-card fm-rise" onClick={(e) => e.stopPropagation()} style={{ width: '100%', maxWidth: wide ? '95vw' : 'calc(var(--shell-max-width) * 0.7)', maxHeight: wide ? '95vh' : '85vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
