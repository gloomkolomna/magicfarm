import { describe, it, expect } from 'vitest';
import {
  slugify,
  renderMarkdown,
  buildToc,
  hasManualToc,
  stripLeadingH1,
  addHeadingIds,
} from '../utils/markdown';

describe('markdown — slugify', () => {
  it('lowercases and converts spaces to hyphens', () => {
    expect(slugify('1. Что это за игра')).toBe('1-что-это-за-игра');
  });

  it('removes em-dashes and collapses to double hyphen', () => {
    expect(slugify('5. Грядки — огород')).toBe('5-грядки--огород');
  });
});

describe('markdown — renderMarkdown', () => {
  it('renders headings and paragraphs', () => {
    const html = renderMarkdown('## Раздел\n\nТекст абзаца');
    expect(html).toContain('<h2>Раздел</h2>');
    expect(html).toContain('<p>Текст абзаца</p>');
  });

  it('renders bold, italic and inline code', () => {
    const html = renderMarkdown('**жирный** и *курсив* и `код`');
    expect(html).toContain('<strong>жирный</strong>');
    expect(html).toContain('<em>курсив</em>');
    expect(html).toContain('<code>код</code>');
  });

  it('renders unordered and ordered lists', () => {
    const html = renderMarkdown('- раз\n- два\n\n1. первый\n2. второй').replace(/\n/g, '');
    expect(html).toContain('<ul><li>раз</li><li>два</li></ul>');
    expect(html).toContain('<ol><li>первый</li><li>второй</li></ol>');
  });

  it('renders a table with header', () => {
    const html = renderMarkdown('| A | B |\n|---|---|\n| 1 | 2 |');
    expect(html).toContain('<table>');
    expect(html).toContain('<th>A</th>');
    expect(html).toContain('<td>1</td>');
  });

  it('renders blockquote and hr', () => {
    const html = renderMarkdown('> цитата\n\n---');
    expect(html).toContain('<blockquote><p>цитата</p></blockquote>');
    expect(html).toContain('<hr>');
  });

  it('escapes raw html', () => {
    const html = renderMarkdown('<script>alert(1)</script>');
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
  });
});

describe('markdown — toc and h1 stripping', () => {
  it('detects manual toc', () => {
    expect(hasManualToc('## Оглавление\n\nтекст')).toBe(true);
    expect(hasManualToc('## Другое')).toBe(false);
  });

  it('builds toc from h2 headings', () => {
    const md = '## Первый раздел\n\n## Второй раздел';
    const toc = buildToc(md);
    expect(toc).toContain('href="#первый-раздел"');
    expect(toc).toContain('href="#второй-раздел"');
  });

  it('strips leading h1', () => {
    const md = '# Правила игры\n\n## Раздел';
    expect(stripLeadingH1(md)).toBe('## Раздел');
  });
});

describe('markdown — addHeadingIds', () => {
  it('assigns slugified ids to h2/h3', () => {
    const root = document.createElement('div');
    root.innerHTML = '<h2>1. Что это за игра</h2><h3>Посадка</h3>';
    addHeadingIds(root);
    expect(root.querySelector('h2')?.id).toBe('1-что-это-за-игра');
    expect(root.querySelector('h3')?.id).toBe('посадка');
  });
});
