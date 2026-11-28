// node tools/review_core_test.js : random 600 operations, invariant must hold after each; export/import round trip
const RC = require("./review_core.js");
let seed = 7; const rnd = (n) => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed % n; };
const H = Array.from({ length: 3000 }, (_, k) => String.fromCodePoint(0x4e00 + (k * 37) % 5000)).join("");
let P = [], pos = 0, id = 1;
while (pos < 2900) { const len = 5 + rnd(30), gap = rnd(4) === 0 ? rnd(5) : 0; const s = pos + gap, e = Math.min(3000, s + len);
  P.push({ id: String(id++), doc: "T.001", vi: "Cau so " + id + ", co dau phay va them chu nua day.", vr: "x", s, e, co: "", pv: "1", dec: "", why: "", note: "", hanEdit: null, who: "", sec: 0 }); pos = e; }
let ops = 0;
for (let t = 0; t < 600; t++) {
  const i = rnd(P.length), op = rnd(5);
  if (op === 0) P = RC.moveEnd(P, i, P[i].e + rnd(11) - 5);
  else if (op === 1) P = RC.moveStart(P, i, P[i].s + rnd(11) - 5);
  else if (op === 2) P = RC.split(P, i, 8 + rnd(10), P[i].s + rnd(P[i].e - P[i].s + 1));
  else if (op === 3 && P.length > 50) P = RC.merge(P, i);
  else { const q = P; P = RC.moveEnd(P, i, -100); P = RC.moveStart(P, Math.min(i, P.length - 1), 99999); void q; }
  if (!RC.check(P, H)) { console.error("INVARIANT BROKEN at op", t, op); process.exit(1); }
  ops++;
}
const pages = [[0, 10], [1500, 11]];
const tsv = RC.toTsv(P, H, pages), P2 = RC.fromTsv(tsv, P.slice(0, 5), H);
if (!RC.check(P2, H)) { console.error("import broke"); process.exit(1); }
// a pair edit/mark does not touch Han offsets
const Q = RC.moveEnd(P, 3, P[3].e + 2); if (Q[3].dec !== "") { console.error("dec not cleared"); process.exit(1); }
if (P.some((p) => p.e === p.s)) { console.error("empty pair created"); process.exit(1); }
const W = [{ id: "1", doc: "d", vi: "abc def ghi", vr: "", s: 0, e: 10, co: "", pv: "1", dec: "", why: "", note: "", hanEdit: null, who: "", sec: 0 }];
if (RC.split(W, 0, 5, 5) !== W || RC.split(W, 0, 4, 5).length !== 2) { console.error("word-boundary split"); process.exit(1); }
const G = [Object.assign({}, W[0], { e: 5 }), Object.assign({}, W[0], { s: 5, e: 8 })];
if (RC.moveEnd(G, 0, 99)[1].e <= RC.moveEnd(G, 0, 99)[1].s) { console.error("next pair emptied"); process.exit(1); }
const Hg = "0123456789", Pg = [Object.assign({}, W[0], { s: 2, e: 5 })];
const tg = RC.toTsv(Pg, Hg, []); if (!/\tkhe\t/.test(tg) || RC.unassigned(Pg, Hg) !== 7 || !RC.check(RC.fromTsv(tg, Pg, Hg), Hg)) { console.error("gaps"); process.exit(1); }
const M0 = [Object.assign({}, W[0], { e: 5, vs: [{ raw: "a" }], hs: [{ k: 1, st: "a" }], hanEdit: "x" }), Object.assign({}, W[0], { s: 5, e: 8, vs: [{ raw: "b" }] })];
const M1 = RC.merge(M0, 0); if (M1[0].vs.length !== 2) { console.error("merge drops vs"); process.exit(1); }
const M2 = RC.moveEnd(M0, 0, 4); if (M2[0].hs[0].st !== "" || M2[0].hanEdit !== null) { console.error("dirty keeps accepted han"); process.exit(1); }
console.log("OK", ops, "ops,", P.length, "pairs, tsv lines", tsv.split("\n").length - 1);
