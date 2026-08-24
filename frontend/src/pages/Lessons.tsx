import { useEffect, useState } from 'react';
import { api, type Lesson } from '../api/endpoints';
import { mediaUrl } from '../api/media';

export default function LessonsPage() {
  const [lessons, setLessons] = useState<Lesson[] | null>(null);
  const [page, setPage] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.lessons()
      .then(setLessons)
      .catch((e: any) => setError(e?.response?.data?.detail || 'Ошибка загрузки уроков'));
  }, []);

  if (lessons === null) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: '8px 6px' }}>
        <div className="fm-card">Загрузка уроков…</div>
      </div>
    );
  }

  if (lessons.length === 0) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: '8px 6px' }}>
        <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>🎬 Видео-уроки</h1>
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Уроков пока нет.</div>
      </div>
    );
  }

  const lesson = lessons[Math.max(0, Math.min(page, lessons.length - 1))];

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: '8px 6px' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>🎬 Видео-уроки</h1>
      {error && <div style={{ fontSize: 12, color: 'var(--danger)', marginBottom: 8 }}>✗ {error}</div>}
      <div key={page} className="fm-rise">
        {lesson.video_url ? (
          <video
            src={mediaUrl(lesson.video_url)}
            poster={lesson.image_url ? mediaUrl(lesson.image_url) : undefined}
            controls
            playsInline
            style={{ width: '100%', maxHeight: '50vh', borderRadius: 12, marginBottom: 12 }}
          />
        ) : lesson.image_url ? (
          <img
            src={mediaUrl(lesson.image_url)}
            alt=""
            style={{ width: '100%', maxHeight: '40vh', objectFit: 'contain', borderRadius: 12, marginBottom: 12 }}
          />
        ) : (
          <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 48, background: 'rgba(255,255,255,0.04)', borderRadius: 12, marginBottom: 12 }}>🎬</div>
        )}
        <div className="fm-story-text">
          <h2 style={{ fontSize: 17, margin: '0 0 6px', color: 'var(--text-primary)' }}>{lesson.title}</h2>
          {lesson.description && (
            <p style={{ fontSize: 15, margin: 0 }}>{lesson.description}</p>
          )}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
        <button className="fm-btn fm-btn-outline" style={{ minWidth: 60 }} disabled={page === 0} onClick={() => setPage(page - 1)}>◀</button>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{page + 1} / {lessons.length}</span>
        <button className="fm-btn fm-btn-outline" style={{ minWidth: 60 }} disabled={page >= lessons.length - 1} onClick={() => setPage(page + 1)}>▶</button>
      </div>
    </div>
  );
}
