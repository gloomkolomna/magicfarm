export function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^\wа-яё\- ]/g, '')
    .replace(/ /g, '-');
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function inline(s: string): string {
  return escapeHtml(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m: string, text: string, url: string) => {
      const extra = url.charAt(0) === '#' ? '' : ' target="_blank" rel="noopener"';
      return `<a href="${url}"${extra}>${text}</a>`;
    });
}

function splitRow(line: string): string[] {
  let s = line.trim();
  if (s.charAt(0) === '|') s = s.slice(1);
  if (s.charAt(s.length - 1) === '|') s = s.slice(0, -1);
  return s.split('|').map((c) => c.trim());
}

function isSeparator(line: string): boolean {
  const s = line.trim();
  if (s.charAt(0) !== '|') return false;
  if (!/^[\s|:\-]+$/.test(s)) return false;
  return s.indexOf('-') !== -1;
}

export function renderMarkdown(md: string): string {
  const lines = md.split('\n');
  const html: string[] = [];
  let i = 0;
  let inList: 'ul' | 'ol' | null = null;

  const closeList = () => {
    if (inList) {
      html.push(`</${inList}>`);
      inList = null;
    }
  };

  while (i < lines.length) {
    const line = lines[i];
    const t = line.trim();

    if (t === '') {
      closeList();
      i++;
      continue;
    }

    if (t === '---') {
      closeList();
      html.push('<hr>');
      i++;
      continue;
    }

    if (/^```/.test(t)) {
      closeList();
      const code: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        code.push(lines[i]);
        i++;
      }
      i++;
      html.push('<pre><code>' + escapeHtml(code.join('\n')) + '</code></pre>');
      continue;
    }

    const h = t.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      closeList();
      const lvl = h[1].length;
      html.push(`<h${lvl}>${inline(h[2])}</h${lvl}>`);
      i++;
      continue;
    }

    if (/^>\s?/.test(t)) {
      closeList();
      const bqLines: string[] = [];
      while (i < lines.length && /^>/.test(lines[i].trim())) {
        bqLines.push(lines[i].trim().replace(/^>\s?/, ''));
        i++;
      }
      html.push(
        '<blockquote>' +
          bqLines
            .map((l) => (l.trim() === '' ? '<br>' : '<p>' + inline(l) + '</p>'))
            .join('') +
          '</blockquote>',
      );
      continue;
    }

    const ol = t.match(/^\d+\.\s+(.*)$/);
    if (ol) {
      if (inList !== 'ol') {
        closeList();
        html.push('<ol>');
        inList = 'ol';
      }
      html.push('<li>' + inline(ol[1]) + '</li>');
      i++;
      continue;
    }

    const ul = t.match(/^[-*]\s+(.*)$/);
    if (ul) {
      if (inList !== 'ul') {
        closeList();
        html.push('<ul>');
        inList = 'ul';
      }
      html.push('<li>' + inline(ul[1]) + '</li>');
      i++;
      continue;
    }

    if (t.charAt(0) === '|' && i + 1 < lines.length && isSeparator(lines[i + 1])) {
      closeList();
      const headerCells = splitRow(t);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().charAt(0) === '|') {
        rows.push(splitRow(lines[i]));
        i++;
      }
      const thead =
        '<thead><tr>' +
        headerCells.map((c) => '<th>' + inline(c) + '</th>').join('') +
        '</tr></thead>';
      const tbody =
        '<tbody>' +
        rows
          .map((r) => '<tr>' + r.map((c) => '<td>' + inline(c) + '</td>').join('') + '</tr>')
          .join('') +
        '</tbody>';
      html.push('<table>' + thead + tbody + '</table>');
      continue;
    }

    closeList();
    html.push('<p>' + inline(t) + '</p>');
    i++;
  }
  closeList();
  return html.join('\n');
}

export function buildToc(md: string): string {
  const lines = md.split('\n');
  const items: string[] = [];
  lines.forEach((line) => {
    const m = line.match(/^(#{1,2})\s+(.*)$/);
    if (m && m[1].length === 2) items.push(m[2]);
  });
  if (items.length === 0) return '';

  const hash: Record<string, boolean> = {};
  let html = '<div class="toc"><div class="toc-title">📖 Оглавление</div><ol>';
  items.forEach((title) => {
    let id = slugify(title);
    let n = 2;
    while (hash[id]) {
      id = slugify(title) + '-' + n;
      n++;
    }
    hash[id] = true;
    html += '<li><a href="#' + id + '">' + escapeHtml(title) + '</a></li>';
  });
  html += '</ol></div>';
  return html;
}

export function hasManualToc(md: string): boolean {
  return /^##\s+(Оглавление|Содержание)\s*$/m.test(md);
}

export function stripLeadingH1(md: string): string {
  const lines = md.split('\n');
  while (lines.length && lines[0].trim() === '') lines.shift();
  if (lines.length && /^#\s/.test(lines[0])) {
    lines.shift();
    while (lines.length && lines[0].trim() === '') lines.shift();
  }
  return lines.join('\n');
}

export function addHeadingIds(root: HTMLElement): void {
  const hash: Record<string, boolean> = {};
  root.querySelectorAll('h2, h3').forEach((el) => {
    const text = el.textContent || '';
    let id = slugify(text);
    let n = 2;
    while (hash[id]) {
      id = slugify(text) + '-' + n;
      n++;
    }
    hash[id] = true;
    el.id = id;
  });
}
