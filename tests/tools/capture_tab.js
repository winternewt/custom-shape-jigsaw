// Track-2 parity harness for the tab generator.
//
// Faithful copy of gentab + lerp + vector helpers from CustomShapeJigsawJs/index.html
// (lines 91-209), but with random() driven by an injected fixed sequence instead of the
// sin-LCG. This isolates the bezier control-point MATH from the platform-libm sin divergence,
// so it can be compared byte/number-for-number against the Python port's gen_tab.
//
// Usage: node capture_tab.js '<json>'  where json = {
//   v1:[x,y], v2:[x,y], mode:"rel"|"abs"|"rabs",
//   tab_rel_size, tab_abs_size, tab_min_size, tab_max_size, tab_jitter, randoms:[...]
// }

const cfg = JSON.parse(process.argv[2]);
let ri = 0;
function random() { return cfg.randoms[ri++]; }
function uniform(min, max) { return min + random() * (max - min); }
function rbool() { return random() > 0.5; }

let flip, a, b, c, d, e, tab_size;
const tj = cfg.tab_jitter;
function next() {
  flip = rbool();
  a = uniform(-tj, tj); b = uniform(-tj, tj); c = uniform(-tj, tj);
  d = uniform(-tj, tj); e = uniform(-tj, tj);
}
function l(v) { return v; }
function w(v) { return v * (flip ? -1.0 : 1.0); }
function p0() { return { l: l(0.0), w: w(0.0) }; }
function p1() { return { l: l(0.2), w: w(a) }; }
function p2() { return { l: l(0.5 + b + d), w: w(-tab_size + c) }; }
function p3() { return { l: l(0.5 - tab_size + b), w: w(tab_size + c) }; }
function p4() { return { l: l(0.5 - 2.0 * tab_size + b - d), w: w(3.0 * tab_size + c) }; }
function p5() { return { l: l(0.5 + 2.0 * tab_size + b - d), w: w(3.0 * tab_size + c) }; }
function p6() { return { l: l(0.5 + tab_size + b), w: w(tab_size + c) }; }
function p7() { return { l: l(0.5 + b + d), w: w(-tab_size + c) }; }
function p8() { return { l: l(0.8), w: w(e) }; }
function p9() { return { l: l(1.0), w: w(0.0) }; }

function sub(v1, v2) { return { x: v1.x - v2.x, y: v1.y - v2.y }; }
function rot90(v) { return { x: -v.y, y: v.x }; }
function add(v1, v2) { return { x: v1.x + v2.x, y: v1.y + v2.y }; }
function mul(s, v) { return { x: s * v.x, y: s * v.y }; }
function lerp(p, v1, v2, op) {
  const dl = sub(v2, v1);
  const dw = rot90(dl);
  let vec = add(v1, mul(p.l, dl));
  vec = add(vec, mul(p.w, dw));
  return op + vec.x + " " + vec.y + " ";
}

function gentab(v1, v2, isnew) {
  const length = Math.hypot(v2.x - v1.x, v2.y - v1.y);
  switch (cfg.mode) {
    case "rel": tab_size = cfg.tab_rel_size; break;
    case "rabs":
      tab_size = cfg.tab_rel_size;
      if (cfg.tab_rel_size * length < cfg.tab_min_size) tab_size = cfg.tab_min_size / length;
      if (cfg.tab_rel_size * length > cfg.tab_max_size) tab_size = cfg.tab_max_size / length;
      break;
    case "abs": tab_size = cfg.tab_abs_size / length; break;
  }
  let str = "";
  next();
  if (isnew) str += lerp(p0(), v1, v2, "M ");
  str += lerp(p1(), v1, v2, "C ");
  str += lerp(p2(), v1, v2, "");
  str += lerp(p3(), v1, v2, "");
  str += lerp(p4(), v1, v2, "C ");
  str += lerp(p5(), v1, v2, "");
  str += lerp(p6(), v1, v2, "");
  str += lerp(p7(), v1, v2, "C ");
  str += lerp(p8(), v1, v2, "");
  str += lerp(p9(), v1, v2, "");
  return str;
}

const v1 = { x: cfg.v1[0], y: cfg.v1[1] };
const v2 = { x: cfg.v2[0], y: cfg.v2[1] };
process.stdout.write(gentab(v1, v2, true));
