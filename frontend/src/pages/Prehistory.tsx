import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../context/SessionContext';
import { api, type DlcStory, type StorySlide } from '../api/endpoints';
import { mediaUrl } from '../api/media';

function SlidePager({ slides, finishLabel, onFinish }: { slides: StorySlide[]; finishLabel: string; onFinish: () => void }) {
  const [page, setPage] = useState(0);
  const [zoomImg, setZoomImg] = useState<string | null>(null);
  const [zoomScale, setZoomScale] = useState(1);
  const [zoomPan, setZoomPan] = useState({ x: 0, y: 0 });
  const zoomBoxRef = useRef<HTMLDivElement>(null);
  const zoomImgRef = useRef<HTMLImageElement>(null);
  const list = slides;
  const slide = list[Math.max(0, Math.min(page, list.length - 1))];

  function next() {
    if (page < list.length - 1) setPage(page + 1);
    else onFinish();
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <div key={page} className="fm-rise">
        {slide.image_url ? (
          <img
            src={mediaUrl(slide.image_url)}
            alt=""
            onClick={() => { setZoomImg(mediaUrl(slide.image_url)); setZoomScale(1); setZoomPan({ x: 0, y: 0 }); }}
            style={{ width: '100%', maxHeight: '45vh', objectFit: 'contain', borderRadius: 12, marginBottom: 12, cursor: 'zoom-in' }}
          />
        ) : (
          <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 48, background: 'rgba(255,255,255,0.04)', borderRadius: 12, marginBottom: 12 }}>📜</div>
        )}
        <div style={{ fontSize: 15, lineHeight: 1.55, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', overflowWrap: 'break-word', wordBreak: 'break-word', background: 'linear-gradient(180deg, rgba(10,16,8,0.60) 0%, rgba(10,16,8,0.48) 100%)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '12px 8px', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)' }}>
          {slide.text || ''}
        </div>
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
        <button className="fm-btn fm-btn-outline" style={{ minWidth: 60 }} disabled={page === 0} onClick={() => setPage(page - 1)}>◀</button>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{page + 1} / {list.length}</span>
        <button className="fm-btn fm-btn-outline" style={{ minWidth: 60 }} disabled={page >= list.length - 1} onClick={() => setPage(page + 1)}>▶</button>
      </div>
      <button className="fm-btn" style={{ width: '100%', marginTop: 12 }} onClick={next}>
        {page < list.length - 1 ? 'Далее →' : finishLabel}
      </button>

      {zoomImg && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.92)', display: 'flex', flexDirection: 'column', padding: 16 }}
          onClick={() => setZoomImg(null)}
        >
          <div style={{ display: 'flex', justifyContent: 'center', gap: 8, alignItems: 'center', marginBottom: 10 }} onClick={(e) => e.stopPropagation()}>
            <button className="fm-btn fm-btn-outline" onClick={() => { setZoomScale((s) => Math.min(4, s + 0.5)); setZoomPan({ x: 0, y: 0 }); }}>＋</button>
            <span style={{ fontSize: 13, color: 'var(--text-muted)', minWidth: 44, textAlign: 'center' }}>{Math.round(zoomScale * 100)}%</span>
            <button className="fm-btn fm-btn-outline" onClick={() => { setZoomScale(1); setZoomPan({ x: 0, y: 0 }); }}>⤢</button>
            <button className="fm-btn fm-btn-outline" onClick={() => { setZoomScale((s) => Math.max(0.5, s - 0.5)); setZoomPan({ x: 0, y: 0 }); }}>−</button>
            <button className="fm-btn fm-btn-outline" onClick={() => setZoomImg(null)}>✕</button>
          </div>
          <div
            ref={zoomBoxRef}
            style={{ flex: 1, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 10, touchAction: 'none', cursor: zoomScale > 1 ? 'grab' : 'default' }}
            onClick={(e) => e.stopPropagation()}
            onPointerDown={(e) => {
              if (zoomScale <= 1) return;
              e.preventDefault();
              const startX = e.clientX;
              const startY = e.clientY;
              const baseX = zoomPan.x;
              const baseY = zoomPan.y;
              const onMove = (ev: PointerEvent) => {
                const dx = ev.clientX - startX;
                const dy = ev.clientY - startY;
                const box = zoomBoxRef.current;
                const img = zoomImgRef.current;
                let maxX = 0;
                let maxY = 0;
                if (box && img) {
                  maxX = Math.max(0, (img.clientWidth * zoomScale - box.clientWidth) / 2);
                  maxY = Math.max(0, (img.clientHeight * zoomScale - box.clientHeight) / 2);
                }
                setZoomPan({
                  x: Math.max(-maxX, Math.min(maxX, baseX + dx)),
                  y: Math.max(-maxY, Math.min(maxY, baseY + dy)),
                });
              };
              const onUp = () => {
                window.removeEventListener('pointermove', onMove);
                window.removeEventListener('pointerup', onUp);
                window.removeEventListener('pointercancel', onUp);
              };
              window.addEventListener('pointermove', onMove);
              window.addEventListener('pointerup', onUp);
              window.addEventListener('pointercancel', onUp);
            }}
          >
            <img
              ref={zoomImgRef}
              src={zoomImg}
              alt=""
              draggable={false}
              style={{
                maxWidth: '100%',
                maxHeight: '100%',
                objectFit: 'contain',
                transform: `translate(${zoomPan.x}px, ${zoomPan.y}px) scale(${zoomScale})`,
                transition: 'transform 0.15s ease',
                borderRadius: 10,
                userSelect: 'none',
                WebkitUserSelect: 'none',
                pointerEvents: 'none',
              }}
            />
          </div>
          {zoomScale > 1 && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', marginTop: 8 }}>
              Тяните изображение, чтобы рассмотреть детали
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Prehistory({ onDone }: { onDone?: () => void }) {
  const [slides, setSlides] = useState<StorySlide[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const finishedRef = useRef(false);

  useEffect(() => {
    api.storySlides()
      .then(setSlides)
      .catch((e: any) => setError(e?.response?.data?.detail || 'Ошибка загрузки предыстории'));
  }, []);

  useEffect(() => {
    if (slides && slides.length === 0 && onDone && !finishedRef.current) {
      finishedRef.current = true;
      api.markStorySeen().catch(() => {});
      onDone();
    }
  }, [slides, onDone]);

  if (slides === null) {
    return <div className="fm-card">Загрузка предыстории…</div>;
  }

  if (slides.length === 0) {
    return <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Предыстория ещё не добавлена.</div>;
  }

  async function finish() {
    if (finishedRef.current) return;
    finishedRef.current = true;
    try {
      await api.markStorySeen();
    } catch { /* ignore */ }
    onDone?.();
  }

  return (
    <div style={{ minHeight: '100%' }}>
      {error && <div style={{ fontSize: 12, color: 'var(--danger)', marginBottom: 8 }}>✗ {error}</div>}
      <SlidePager slides={slides} finishLabel={onDone ? 'Начать игру' : 'Закрыть'} onFinish={finish} />
    </div>
  );
}

export function DlcStoryOverlay({ locationCode, name, emoji, onClose }: { locationCode: string; name: string; emoji: string; onClose: () => void }) {
  const [status, setStatus] = useState<DlcStory | null>(null);
  const [intro, setIntro] = useState(true);
  const doneRef = useRef(false);

  useEffect(() => {
    api.storyDlc(locationCode)
      .then(setStatus)
      .catch(() => setStatus({ slides: [], seen: true }));
  }, [locationCode]);

  async function finish() {
    if (doneRef.current) return;
    doneRef.current = true;
    try {
      await api.markStoryDlcSeen(locationCode);
    } catch { /* ignore */ }
    onClose();
  }

  if (status === null || status.seen || status.slides.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 70,
        background: 'rgba(8,12,6,0.97)', backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '12px 8px',
      }}
    >
      <div style={{ width: '100%', maxHeight: '90vh', overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {intro ? (
          <div className="fm-pop" style={{ textAlign: 'center', padding: '24px 8px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
            <div style={{ fontSize: 'clamp(56px, 20vw, 110px)', lineHeight: 1 }}>{emoji}</div>
            <h1 style={{ fontSize: 'clamp(22px, 7vw, 32px)', margin: 0 }}>{name}</h1>
            <p style={{ fontSize: 15, color: 'var(--text-secondary)', margin: 0 }}>Вы открыли новое дополнение. Узнайте его историю.</p>
            <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
              <button className="fm-btn fm-btn-sm" onClick={() => setIntro(false)}>▶ Начать историю</button>
              <button className="fm-btn fm-btn-sm fm-btn-outline" onClick={finish}>Пропустить</button>
            </div>
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <span style={{ fontSize: 22 }}>{emoji}</span>
              <strong style={{ fontSize: 17 }}>{name} — история</strong>
              <span style={{ flex: 1 }} />
              <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={finish}>Пропустить</button>
            </div>
            <SlidePager slides={status.slides} finishLabel="Готово" onFinish={finish} />
          </>
        )}
      </div>
    </div>
  );
}

export function DlcStoryGate({ locationCode, name, emoji, children }: { locationCode: string; name: string; emoji: string; children: ReactNode }) {
  const { user } = useSession();
  const [status, setStatus] = useState<DlcStory | null>(null);
  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    if (isAdmin) return;
    let cancelled = false;
    api.storyDlc(locationCode)
      .then((s) => { if (!cancelled) setStatus(s); })
      .catch(() => { if (!cancelled) setStatus({ slides: [], seen: true }); });
    return () => { cancelled = true; };
  }, [locationCode, isAdmin]);

  return (
    <>
      {children}
      {!isAdmin && status && !status.seen && status.slides.length > 0 && (
        <DlcStoryOverlay locationCode={locationCode} name={name} emoji={emoji} onClose={() => setStatus((s) => (s ? { ...s, seen: true } : s))} />
      )}
    </>
  );
}

export function PrehistoryPage() {
  const nav = useNavigate();
  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: '8px 6px' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>📜 Предыстория</h1>
      <Prehistory onDone={() => nav(-1)} />
    </div>
  );
}
