export default function SpritePedestal({
  url,
  emoji,
  height = 120,
  onZoom,
}: {
  url?: string | null;
  emoji?: string | null;
  height?: number;
  onZoom?: (u: string) => void;
}) {
  if (!url && !emoji) return null;
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--surface-strong)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: '10px 8px',
        marginBottom: 10,
        cursor: url && onZoom ? 'zoom-in' : 'default',
      }}
      onClick={() => { if (url && onZoom) onZoom(url); }}
    >
      {url ? (
        <img src={url} alt="" style={{ height, maxWidth: '100%', objectFit: 'contain' }} />
      ) : (
        <span style={{ fontSize: Math.round(height * 0.55), lineHeight: 1 }}>{emoji}</span>
      )}
    </div>
  );
}
