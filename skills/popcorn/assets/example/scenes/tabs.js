// the recipe tabs both scenes share, at the same places, so the answer starts where the problem ended
const TAB_AT = [[70, 92], [150, 128], [230, 164], [110, 228], [190, 264], [270, 300]];
function recipeTabs() {
  return TAB_AT.map(([x, y]) => {
    const t = el('div', 'sc-tab abs', null, '<div class="hd"><i></i><i></i><i></i></div>'); box(t, x, y);
    const b = textBlock(t, 14, 42, 200, 5, { gap: 9, h: 9 });
    b.bars.forEach((r) => (r.style.opacity = 1));
    return t;
  });
}
