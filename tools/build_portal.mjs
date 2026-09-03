import { cp, mkdir, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const source = resolve('spina_portal');
const output = resolve('dist');

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(source, output, {
  recursive: true,
  filter: (path) => !path.includes(`${resolve('spina_portal', 'tests')}`),
});
await writeFile(
  resolve(output, '_build.json'),
  JSON.stringify(
    {
      application: 'Spina',
      surface: 'four-role-pwa',
      version: '0.1.0',
      built_at: new Date().toISOString(),
    },
    null,
    2,
  ),
  'utf8',
);

console.log(`Spina portal built at ${output}`);
