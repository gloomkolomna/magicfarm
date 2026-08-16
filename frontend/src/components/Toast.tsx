export default function Toast({ text, onClose }: { text: string | null; onClose: () => void }) {
  if (!text) return null;
  return (
    <div
      className="fm-card fm-rise"
      role="status"
      style={{
        position: 'fixed',
        top: 46,
        left: 0,
        right: 0,
        margin: '0 auto',
        zIndex: 110,
        width: 'max-content',
        maxWidth: 'calc(var(--shell-max-width) - 24px)',
        fontSize: 14,
        textAlign: 'center',
        cursor: 'pointer',
        background: 'linear-gradient(180deg, rgba(15,22,12,0.92) 0%, rgba(15,22,12,0.85) 100%)',
        boxShadow: '0 10px 28px rgba(0,0,0,0.5)',
      }}
      onClick={onClose}
    >
      {text}
    </div>
  );
}
