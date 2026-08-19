import { useEffect, useState } from 'react';
import { api } from '../api/endpoints';
import { mediaUrl } from '../api/media';

const IMG_W = 1200;
const IMG_H = 896;

function computeOverflow() {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const scale = Math.max(vw / IMG_W, vh / IMG_H);
  const renderedW = IMG_W * scale;
  const renderedH = IMG_H * scale;
  return { x: Math.max(0, renderedW - vw), y: Math.max(0, renderedH - vh) };
}

export default function InfirmaryBackground() {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.getInfirmaryBackground()
      .then((d) => { if (!cancelled && d.url) setUrl(d.url); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!url) return null;

  const overflow = computeOverflow();
  const overflowStyle = {
    width: `calc(100% + ${overflow.x}px)`,
    height: `calc(100% + ${overflow.y}px)`,
  };

  return (
    <div aria-hidden="true" style={{ position: 'fixed', inset: 0, zIndex: -2, overflow: 'hidden' }}>
      <img
        src={mediaUrl(url)}
        alt=""
        draggable={false}
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          minWidth: '100%',
          minHeight: '100%',
          transform: 'translate(-50%, -50%)',
          objectFit: 'cover',
          ...overflowStyle,
          userSelect: 'none',
          WebkitUserSelect: 'none',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(ellipse at center, transparent 0%, rgba(15,22,12,0.35) 75%, rgba(10,16,8,0.55) 100%)',
        }}
      />
    </div>
  );
}
