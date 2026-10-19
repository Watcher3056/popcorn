// Frame-exact motion kit. Every moving thing is a list of (time, value) points per property; seek(t) sets all of
// them for time t, so the renderer can take any frame at any rate and get the same picture every time.
// A scene page: <div id="stage"></div>, /kit/kit.css and /kit/kit.js, then its own script that builds the scene
// with these helpers and ends with  window.TOTAL = <length in ms>; finalize();
// Properties: o (opacity), x, y (px), s (scale), sx (horizontal scale from the left edge), r (rotation, deg),
// cw (visible width from the left, %), ch (visible height from the top, %).
// Times are page milliseconds. Nothing may read the clock: a frame depends on t alone.
const TRACKS = new Map();
const HOOKS = [];
// sound cues for the video: [time, kind]; a GIF ignores them. Kinds: see the toolkit reference.
window.SFX = [];
const sfx = (t, k) => window.SFX.push([t, k]);
const EASE = {
  io: (u) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2),
  out: (u) => 1 - Math.pow(1 - u, 3),
  in: (u) => u * u * u,
  lin: (u) => u,
  step: (u) => (u < 1 ? 0 : 1),
};

// a point of a property's track; the ease shapes the move that ends at this point
function pt(node, prop, t, v, ease = 'io') {
  if (!TRACKS.has(node)) TRACKS.set(node, {});
  const m = TRACKS.get(node);
  (m[prop] = m[prop] || []).push([t, v, ease]);
  return node;
}
function val(pts, t) {
  if (t <= pts[0][0]) return pts[0][1];
  for (let i = 1; i < pts.length; i++) {
    const [t1, v1, e] = pts[i], [t0, v0] = pts[i - 1];
    if (t <= t1) return t1 === t0 ? v1 : v0 + (v1 - v0) * EASE[e]((t - t0) / (t1 - t0));
  }
  return pts[pts.length - 1][1];
}
window.seek = (t) => {
  for (const [node, m] of TRACKS) {
    const g = (k, d) => (m[k] ? val(m[k], t) : d);
    if (m.o) node.style.opacity = g('o', 1);
    if (m.x || m.y || m.s || m.sx || m.r) node.style.transform = `translate(${g('x', 0)}px, ${g('y', 0)}px) rotate(${g('r', 0)}deg) scale(${g('s', 1)}) scaleX(${g('sx', 1)})`;
    if (m.cw || m.ch) node.style.clipPath = `inset(0 ${100 - g('cw', 100)}% ${100 - g('ch', 100)}% 0)`;
  }
  for (const h of HOOKS) h(t);
  return 1;
};
// state that isn't a number (a counter's text, a class that switches, etc.): fn(t) runs at every seek
function every(fn) { HOOKS.push(fn); }
window.finalize = () => { for (const m of TRACKS.values()) for (const k in m) m[k].sort((a, b) => a[0] - b[0]); window.seek(0); return 1; };

// ---- building blocks ----
let SEED = 7; const rnd = () => ((SEED = (SEED * 16807) % 2147483647) / 2147483647);
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
function el(tag, cls, parent, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; (parent || document.getElementById('stage')).append(e); return e; }
function box(e, x, y, w, h) { Object.assign(e.style, { left: x + 'px', top: y + 'px' }); if (w) e.style.width = w + 'px'; if (h) e.style.height = h + 'px'; return e; }
function show(e, t, dur = 380, dy = 14) { pt(e, 'o', t, 0); pt(e, 'o', t + dur, 1); if (dy) { pt(e, 'y', t, dy); pt(e, 'y', t + dur, 0); } return e; }
function hide(e, t, dur = 320) { pt(e, 'o', t, 1); pt(e, 'o', t + dur, 0); return e; }
function pop(e, t, dur = 420, cue = 'pop') { if (cue) sfx(t, cue); pt(e, 'o', t, 0); pt(e, 'o', t + dur * 0.6, 1); pt(e, 's', t, 0.9); pt(e, 's', t + dur, 1); return e; }
// a move from one place to another (offsets from the element's own box)
function slide(e, t0, t1, from, to, ease = 'io') { pt(e, 'x', t0, from[0]); pt(e, 'y', t0, from[1]); pt(e, 'x', t1, to[0], ease); pt(e, 'y', t1, to[1], ease); return e; }
// one text replaces another in the same place: the old one is gone before the new one comes, so they never overlap
function swap(oldEl, newEl, t, dur = 260) { hide(oldEl, t, dur); show(newEl, t + dur, dur, 0); return newEl; }

// a big title card over the stage, and a caption chip
function title(html, sub, tone, t0, t1) {
  const c = el('div', 'title ' + (tone || ''), null, '<h1>' + html + '</h1>' + (sub ? '<p>' + sub + '</p>' : ''));
  sfx(t0, 'bloom'); show(c, t0, 420, 18); if (t1 != null) hide(c, t1, 360);
  return c;
}
function chip(text, tone, t0, t1, y = 26) {
  const c = el('div', 'chip ' + (tone || ''), null, '<i>' + text + '</i>'); c.style.top = y + 'px';
  show(c, t0, 300, -8); if (t1 != null) hide(c, t1, 260);
  return c;
}
// the pointer: [t, x, y] stops; clicks at [t, x, y] with a ripple and a click sound
function cursor(stops, clicks, t0, t1) {
  const c = el('div', 'cursor', null, '<svg width="22" height="26" viewBox="0 0 22 26"><path d="M1 1 L1 20 L6 15.5 L9.6 23.5 L13.2 22 L9.7 14.4 L16 14.4 Z" fill="#fff" stroke="#000" stroke-width="1.6" stroke-linejoin="round"/></svg>');
  for (const [t, x, y] of stops) { pt(c, 'x', t, x); pt(c, 'y', t, y); }
  pt(c, 'o', t0, 0); pt(c, 'o', t0 + 200, 1); if (t1 != null) { pt(c, 'o', t1, 1); pt(c, 'o', t1 + 200, 0); }
  for (const [t, x, y] of clicks || []) {
    sfx(t, 'click');
    const r = el('div', 'ripple'); box(r, x - 20, y - 20, 40, 40);
    pt(r, 'o', t - 1, 0); pt(r, 'o', t, 0.9); pt(r, 'o', t + 450, 0); pt(r, 's', t, 0.3); pt(r, 's', t + 450, 1.4);
    pt(c, 's', t - 1, 1); pt(c, 's', t + 60, 0.85); pt(c, 's', t + 180, 1);
  }
  return c;
}
// a red ✕ stamped on the bad thing, and a green ✓ on the good one
function xmark(x, y, t, parent = null, size = 72) { return mark('xmark', '✕', x, y, t, parent, size, 'fail'); }
function okmark(x, y, t, parent = null, size = 72) { return mark('okmark', '✓', x, y, t, parent, size, 'chime'); }
function mark(cls, glyph, x, y, t, parent, size, cue) {
  const m = el('div', cls + ' abs', parent, glyph); box(m, x, y, size, size); m.style.fontSize = Math.round(size * 0.56) + 'px';
  pt(m, 'o', t, 0); pt(m, 'o', t + 120, 1); pt(m, 's', t, 1.8); pt(m, 's', t + 280, 1); sfx(t, cue);
  return m;
}
// a light outline that draws the eye to a thing, instead of darkening everything else
function ring(target, t, tone = 'good', t1 = null) {
  const r = el('div', 'ring ' + tone, target); pt(r, 'o', t, 0); pt(r, 'o', t + 300, 1); if (t1 != null) hide(r, t1, 260); return r;
}
// text typed in from t0 at cps characters a second, with typing ticks under it
function typeText(node, text, t0, cps = 28) {
  const n = [...text].length, dur = (n / cps) * 1000;
  node.textContent = ''; sfx(t0, 'type:' + Math.round(dur));
  every((t) => { const k = Math.max(0, Math.min(n, Math.floor(((t - t0) / dur) * n))); const s = [...text].slice(0, k).join(''); if (node.textContent !== s) node.textContent = s; });
  return t0 + dur;
}
// a number that runs from a to b between t0 and t1
function counter(node, a, b, t0, t1, fmt = (v) => Math.round(v).toLocaleString('en-US')) {
  every((t) => { const u = Math.max(0, Math.min(1, (t - t0) / (t1 - t0))); node.textContent = fmt(a + (b - a) * EASE.io(u)); });
  return node;
}
// abstract text: grey bars instead of real lines, the simplified look of "a lot of text"
function textBlock(parent, x, y, w, lines, { gap = 9, h = 10, minW = 55 } = {}) {
  const b = el('div', 'tblock abs', parent); box(b, x, y, w);
  const bars = [];
  for (let i = 0; i < lines; i++) { const r = el('div', 'bar', b); r.style.height = h + 'px'; r.style.marginBottom = gap + 'px'; r.style.width = (minW + rnd() * (100 - minW)) + '%'; bars.push(r); }
  return { el: b, bars };
}
// the bars appear one by one between t0 and t1; with view = its clipping box, the text scrolls up as it grows
function stream(block, t0, t1, view = null) {
  const B = block.bars, step = (t1 - t0) / B.length;
  B.forEach((b, i) => { const t = t0 + i * step; pt(b, 'o', t, 0); pt(b, 'o', t + 90, 1); pt(b, 'sx', t, 0.15); pt(b, 'sx', t + 140, 1); });
  if (view) {
    const vh = view.clientHeight, top = (b) => b.offsetTop;
    pt(block.el, 'y', t0, 0, 'lin');
    B.forEach((b, i) => { const over = top(b) + b.offsetHeight - vh + 16; if (over > 0) pt(block.el, 'y', t0 + i * step + 140, -over, 'lin'); });
  }
  sfx(t0, 'type:' + Math.round(t1 - t0));
  return block;
}
// a layer the camera moves over: cam() pans and zooms it
function world(parent = null) { const w = el('div', 'world abs', parent); pt(w, 'x', 0, 0); pt(w, 'y', 0, 0); pt(w, 's', 0, 1); return w; }
function cam(w, t0, t1, from, to, ease = 'io') {
  const [x0, y0, s0 = 1] = from, [x1, y1, s1 = 1] = to;
  pt(w, 'x', t0, x0); pt(w, 'y', t0, y0); pt(w, 's', t0, s0); pt(w, 'x', t1, x1, ease); pt(w, 'y', t1, y1, ease); pt(w, 's', t1, s1, ease);
}
// before → after in one frame: the "after" picture wipes over the "before" from the left, with a handle on the edge
function compare(parent, x, y, w, h, beforeHtml, afterHtml, t0, t1, labels = ['Before', 'After']) {
  const c = el('div', 'compare abs', parent); box(c, x, y, w, h);
  const a = el('div', 'side before', c, beforeHtml), b = el('div', 'side after', c, afterHtml);
  el('div', 'lbl l', a, labels[0]); el('div', 'lbl r', b, labels[1]);
  const hd = el('div', 'handle', c);
  pt(b, 'cw', t0, 0); pt(b, 'cw', t1, 100);
  every((t) => { const u = Math.max(0, Math.min(1, (t - t0) / (t1 - t0))); hd.style.left = (EASE.io(u) * w - 1.5) + 'px'; hd.style.opacity = u > 0 && u < 1 ? 1 : 0; });
  return { el: c, before: a, after: b };
}
function at(node) { const r = node.getBoundingClientRect(), s = document.getElementById('stage').getBoundingClientRect(); return [r.left - s.left + r.width / 2, r.top - s.top + r.height / 2]; }

// a story label in the corner for the whole scene, set from the plan: page.html?tag=<text>&tone=bad|good
// It comes in after the transition into the scene (tagin=<ms>, default 350), so two labels never blend in one place;
// tagin=0 keeps it from the first frame (the same label carried on from the scene before).
(() => {
  const q = new URLSearchParams(location.search), tag = q.get('tag');
  if (!tag) return;
  const tin = +(q.get('tagin') ?? 350);
  const put = () => {
    const t = document.createElement('div'); t.className = 'storytag ' + (q.get('tone') || 'bad'); t.textContent = tag; document.getElementById('stage').append(t);
    if (tin > 0) { pt(t, 'o', tin, 0); pt(t, 'o', tin + 250, 1); }
  };
  document.getElementById('stage') ? put() : document.addEventListener('DOMContentLoaded', put);
})();
