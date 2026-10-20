// Still frames in one browser: storyboard slides, thumbnails, covers, a check of one moment.
// Usage: node stills.mjs <jobs.json>   jobs: [{ url, t, out, width, height, scale, scheme }]
// A page that repeats (several frames of one scene) loads once.
import { page } from './cdp.mjs';
import fs from 'node:fs';

const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let p = null, key = '', loaded = '';
for (const j of jobs) {
  const k = [j.width, j.height, j.scale, j.scheme || 'light'].join('x');
  if (k !== key) { if (p) p.close(); p = await page({ width: j.width, height: j.height, scale: j.scale, scheme: j.scheme || 'light' }); key = k; loaded = ''; }
  if (j.url !== loaded) { await p.open(j.url); loaded = j.url; }
  await p.at(j.t);
  await p.shot(j.out);
  console.log(j.out);
}
process.exit(0);
