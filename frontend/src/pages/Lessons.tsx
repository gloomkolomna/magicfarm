import { useEffect, useState } from 'react';
import { api, type Lesson, LESSON_CATEGORIES } from '../api/endpoints';
import { mediaUrl } from '../api/media';

export default function LessonsPage() {
  const [lessons, setLessons] = useState<Lesson[] | null>(null);
  const [cat, setCat] = useState(LESSON_CATEGORIES[0].code);
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

  const filtered = lessons.filter((l) => l.category === cat);
  const current = Math.min(page, Math.max(0, filtered.length - 1));

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: '8px 6px' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>🎬 Видеоуроки</h1>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
        {LESSON_CATEGORIES.map((c) => (
          <button
            key={c.code}
            className="fm-btn fm-btn-sm"
            style={cat === c.code ? undefined : { opacity: 0.7 }}
            onClick={() => { setCat(c.code); setPage(0); }}
          >
            {c.label}
          </button>
        ))}
      </div>
      {error && <div style={{ fontSize: 12, color: 'var(--danger)', marginBottom: 8 }}>✗ {error}</div>}
      {filtered.length === 0 ? (
        <div className="fm-card" style={{ color: 'var(--text-muted)' }}>
          {lessons.length === 0 ? 'Уроков пока нет.' : 'В этой категории уроков пока нет.'}
        </div>
      ) : (
        <>
          <div key={`${cat}-${page}`} className="fm-rise">
            {(() => {
              const lesson = filtered[current];
              return (
                <>
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
                </>
              );
            })()}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
            <button className="fm-btn fm-btn-outline fm-view-allow" style={{ minWidth: 60 }} disabled={current === 0} onClick={() => setPage(current - 1)}>◀</button>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{current + 1} / {filtered.length}</span>
            <button className="fm-btn fm-btn-outline fm-view-allow" style={{ minWidth: 60 }} disabled={current >= filtered.length - 1} onClick={() => setPage(current + 1)}>▶</button>
          </div>
        </>
      )}
    </div>
  );
}
