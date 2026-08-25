import { useEffect, useRef, useState } from 'react';
import { addHeadingIds, buildToc, hasManualToc, renderMarkdown, stripLeadingH1 } from '../utils/markdown';

const GUIDE_URL = window.location.origin + '/magicfarm/game/guide.md';

export default function RulesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tocHtml, setTocHtml] = useState('');
  const [contentHtml, setContentHtml] = useState('');
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(GUIDE_URL)
      .then((r) => {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.text();
      })
      .then((md) => {
        if (cancelled) return;
        const cleaned = stripLeadingH1(md);
        setTocHtml(hasManualToc(cleaned) ? '' : buildToc(cleaned));
        setContentHtml(renderMarkdown(cleaned));
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setLoading(false);
        setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (contentHtml && contentRef.current) {
      addHeadingIds(contentRef.current);
    }
  }, [contentHtml]);

  return (
    <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: '8px 6px' }}>
      <h1 style={{ fontSize: 20, margin: '0 0 10px' }}>📜 Правила игры</h1>
      {loading ? (
        <div className="fm-card">Загрузка правил…</div>
      ) : error ? (
        <div className="fm-card" style={{ color: 'var(--danger)' }}>
          ✗ Не удалось загрузить правила. Попробуйте обновить страницу.
        </div>
      ) : (
        <div className="fm-rules">
          {tocHtml ? <div dangerouslySetInnerHTML={{ __html: tocHtml }} /> : null}
          <div ref={contentRef} dangerouslySetInnerHTML={{ __html: contentHtml }} />
        </div>
      )}
    </div>
  );
}
