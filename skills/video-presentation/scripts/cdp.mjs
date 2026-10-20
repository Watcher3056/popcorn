// A minimal Chrome DevTools Protocol client: open a tab in a headless browser, load a scene page, seek it to a time
// and take the frame. CDP_PORT picks one of several browsers, so scenes can render side by side.
import fs from 'node:fs';

const PORT = process.env.CDP_PORT || 9333;
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function page({ width = 960, height = 540, scale = 1, scheme = 'light' } = {}) {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  let t = list.find((x) => x.type === 'page');
  if (!t) t = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener('open', r, { once: true }));
  let id = 0;
  const wait = new Map();
  ws.addEventListener('message', (e) => {
    const m = JSON.parse(e.data);
    if (m.id && wait.has(m.id)) { const { res, rej } = wait.get(m.id); wait.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  });
  const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; wait.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: scale, mobile: false });
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: scheme }, { name: 'prefers-reduced-motion', value: 'no-preference' }] });
  try { await send('Emulation.setLocaleOverride', { locale: 'en-US' }); } catch { /* already set */ }
  const api = {
    send,
    async js(expr) {
      const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 400));
      return r.result.value;
    },
    // loads a scene page and waits until this very load (not the tab's previous page) has built its timeline and has
    // its images and fonts; a busy browser can take seconds, so a load that doesn't get ready is retried
    async open(url) {
      for (let tries = 0; ; tries++) {
        const token = String(Date.now()) + tries;
        await send('Page.navigate', { url: url + (url.includes('?') ? '&' : '?') + 'v=' + token });
        const READY = `[location.search.includes('v=${token}'), typeof seek === 'function', typeof TOTAL === 'number', document.readyState === 'complete', [...document.images].every((i) => i.complete), [...document.querySelectorAll('video')].every((v) => v.readyState >= 2)]`;
        let state = null;
        for (let k = 0; k < 150; k++) {
          state = await api.js(READY).catch((e) => String(e).slice(0, 120));
          if (Array.isArray(state) && state.every(Boolean)) { await api.js('document.fonts.ready.then(() => 1)'); return; }
          await sleep(100);
        }
        if (tries >= 3) throw new Error(url + ': the page did not get ready: ' + JSON.stringify(state));
        console.log(url, 'not ready, loading again:', JSON.stringify(state));
      }
    },
    // the frame at page time t: seek (and wait for any recording in the scene to reach its frame), then two animation
    // frames so the browser has painted it
    async at(t) { await api.js(`Promise.resolve(seek(${t})).then(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(1)))))`); },
    async shot(file, format = 'png', quality = 90) {
      const r = await send('Page.captureScreenshot', format === 'jpeg' ? { format, quality } : { format });
      const buf = Buffer.from(r.data, 'base64');
      if (file) fs.writeFileSync(file, buf);
      return buf;
    },
    close() { ws.close(); },
  };
  return api;
}
