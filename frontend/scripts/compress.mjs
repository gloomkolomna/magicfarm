import { readdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join, extname } from 'node:path';
import { gzip } from 'node:zlib';
import { promisify } from 'node:util';

const gzipAsync = promisify(gzip);

const ASSETS_DIR = fileURLToPath(new URL('../dist/assets/', import.meta.url));
const EXTENSIONS = new Set(['.js', '.css']);

async function main() {
  console.log('Предсжатие ассетов (.gz)...');
  const entries = await readdir(ASSETS_DIR, { withFileTypes: true });
  let count = 0;
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    if (entry.name.endsWith('.gz')) continue;
    if (!EXTENSIONS.has(extname(entry.name))) continue;
    const content = await readFile(join(ASSETS_DIR, entry.name));
    const gz = await gzipAsync(content, { level: 9 });
    await writeFile(join(ASSETS_DIR, `${entry.name}.gz`), gz);
    console.log(`  ${entry.name}.gz  ${(gz.length / 1024).toFixed(1)} KB`);
    count++;
  }
  console.log(count ? `Готово: ${count} файлов.` : 'Нет файлов для сжатия.');
}

main().catch((e) => {
  console.error('Ошибка сжатия:', e.message);
  process.exit(1);
});
