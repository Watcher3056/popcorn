// Renders one scene: page time t0..t1 at a playback speed, frame by frame, and the scene's sound cues in its own
// seconds. Usage: node render.mjs <url> <outDir> <t0> <t1> <speed> <fps> <scale> <stageW> <stageH> [scheme]
// Env: CDP_PORT (which browser), FMT=png|jpeg (frame files), SEG_KEY (stored in meta.json for the cache)
import { page } from './cdp.mjs';
import fs from 'node:fs';

const [url, out, t0, t1, speed, fps, scale, w, h, scheme = 'light'] = process.argv.slice(2);
const p = await page({ width: +w, height: +h, scale: +scale, scheme });
await p.open(url);
fs.rmSync(out, { recursive: true, force: true }); fs.mkdirSync(out, { recursive: true });
const FMT = process.env.FMT || 'png', EXT = FMT === 'jpeg' ? 'jpg' : 'png';
const step = (1000 / +fps) * +speed;
let n = 0;
for (let t = +t0; t < +t1 - 1e-6; t += step) {
  await p.at(t);
  await p.shot(`${out}/${String(n++).padStart(5, '0')}.${EXT}`, FMT);
}
const cues = JSON.parse(await p.js('JSON.stringify(window.SFX || [])'))
  .filter(([t]) => t >= +t0 && t < +t1).map(([t, k]) => [(t - +t0) / 1000 / +speed, k]);
fs.writeFileSync(`${out}/meta.json`, JSON.stringify({ url, t0: +t0, t1: +t1, speed: +speed, fps: +fps, frames: n, secs: n / +fps, cues, ext: EXT, key: process.env.SEG_KEY || '' }));
console.log(url.replace(/^https?:\/\/[^/]+/, ''), t0, t1, 'x' + speed, n, 'frames', (n / +fps).toFixed(2), 's', cues.length, 'cues');
process.exit(0);
