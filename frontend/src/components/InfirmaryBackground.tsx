import { useEffect, useState } from 'react';
import { api } from '../api/endpoints';
import { mediaUrl } from '../api/media';

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

  return (
    <div aria-hidden="true" style={{ position: 'fixed', inset: 0, zIndex: -2, overflow: 'hidden' }}>
      <img
        src={mediaUrl(url)}
        alt=""
        draggable={false}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          objectPosition: 'center center',
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
