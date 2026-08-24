import { useRef, useState } from 'react';
import { mediaUrl } from '../api/media';

const MIN_SCALE = 0.1;
const MAX_SCALE = 4;
const ZOOM_STEP = 1.25;

const zoomBtn: React.CSSProperties = {
  width: 44, height: 44, borderRadius: 22,
  border: '1px solid rgba(255,255,255,0.25)',
  background: 'rgba(20,25,20,0.78)', color: '#f3ead0',
  fontSize: 20, lineHeight: 1, cursor: 'pointer',
  backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: 0,
};

interface Props {
  mapUrl: string | null;
  name: string;
  emoji?: string;
  onBack: () => void;
  backLabel?: string;
  children?: React.ReactNode;
}

export default function LocationMap({ mapUrl, name, emoji, onBack, backLabel = 'Поля', children }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [imgNaturalW, setImgNaturalW] = useState<number | null>(null);
  const [imgNaturalH, setImgNaturalH] = useState<number | null>(null);
  const [scale, setScale] = useState(1);

  function zoomIn() { setScale((s) => Math.max(MIN_SCALE, Math.min(MAX_SCALE, s * ZOOM_STEP))); }
  function zoomOut() { setScale((s) => Math.max(MIN_SCALE, Math.min(MAX_SCALE, s / ZOOM_STEP))); }
  function resetScale() { setScale(1); }
  function fitToScreen() {
    const vp = scrollRef.current;
    if (!vp || !imgNaturalW || !imgNaturalH) return;
    const s = Math.min(vp.clientWidth / imgNaturalW, vp.clientHeight / imgNaturalH);
    setScale(Math.max(MIN_SCALE, Math.min(1, s)));
  }

  return (
    <>
      <div
        ref={scrollRef}
        style={{
          position: 'fixed', inset: 0, top: '38px', zIndex: 0, overflow: 'auto',
          overscrollBehavior: 'contain', backgroundColor: '#1a2414',
        }}
      >
        {mapUrl ? (
          <div style={{ position: 'relative', display: 'inline-block', lineHeight: 0, width: imgNaturalW ? `${Math.round(imgNaturalW * scale)}px` : '100%' }}>
            <img
              src={mediaUrl(mapUrl)}
              alt=""
              style={{ display: 'block', width: '100%' }}
              onLoad={(e) => { setImgNaturalW((e.target as HTMLImageElement).naturalWidth); setImgNaturalH((e.target as HTMLImageElement).naturalHeight); }}
            />
            {children}
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: 16, padding: 20 }}>Карта не загружена</div>
        )}
      </div>

      {mapUrl && (
        <div className="fm-view-allow" style={{ position: 'fixed', right: 12, bottom: 'calc(16px + var(--vk-inset-bottom, 0px))', zIndex: 25, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' }}>
          <button onClick={zoomIn} aria-label="Увеличить" style={zoomBtn}>＋</button>
          <button onClick={resetScale} aria-label="Реальный масштаб" title="Реальный масштаб (100%)" style={{ ...zoomBtn, fontSize: 13, fontWeight: 700 }}>{Math.round(scale * 100)}%</button>
          <button onClick={zoomOut} aria-label="Уменьшить" style={zoomBtn}>−</button>
          <button onClick={fitToScreen} aria-label="Вместить в экран" title="Вместить поле в экран" style={zoomBtn}>⤢</button>
        </div>
      )}

      <div
        className="fm-view-allow"
        style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 20,
          display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
          paddingTop: '6px',
          background: 'linear-gradient(180deg, rgba(10,16,8,0.92) 0%, rgba(10,16,8,0.78) 100%)',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
        }}
      >
        <button className="fm-btn fm-btn-xs fm-btn-outline" onClick={onBack} style={{ background: 'rgba(255,255,255,0.14)', color: '#ffffff', borderColor: 'rgba(255,255,255,0.25)' }}>
          ← {backLabel}
        </button>
        <h1 style={{ margin: 0, flex: 1, fontSize: 18, color: '#ffffff', textShadow: '0 1px 3px rgba(0,0,0,0.7)' }}>
          {emoji ? `${emoji} ` : ''}{name}
        </h1>
      </div>
    </>
  );
}
