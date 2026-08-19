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
          top: '50%',
          left: '50%',
          minWidth: '100%',
          minHeight: '100%',
          transform: 'translate(-50%, -50%)',
          objectFit: 'cover',
          userSelect: 'none',
          WebkitUserSelect: 'none',
          pointerEvents: 'none',
        }}
      />
    </div>
  );
}
