import { readdir } from 'node:fs/promises';
import { extname, join } from 'node:path';
import { spawnSync } from 'node:child_process';

async function filesUnder(directory) {
  const output = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      output.push(...(await filesUnder(path)));
    } else if (['.js', '.mjs'].includes(extname(entry.name))) {
      output.push(path);
    }
  }
  return output;
}

const files = [
  ...(await filesUnder('spina_portal/assets')),
  ...(await filesUnder('spina_portal/tests')),
  'spina_portal/sw.js',
];

for (const file of files) {
  const result = spawnSync(process.execPath, ['--check', file], {
    encoding: 'utf8',
    stdio: 'pipe',
  });
  if (result.status !== 0) {
    process.stderr.write(result.stdout || '');
    process.stderr.write(result.stderr || '');
    throw new Error(`JavaScript syntax check failed: ${file}`);
  }
}

console.log(`SPINA portal syntax check passed for ${files.length} modules.`);
