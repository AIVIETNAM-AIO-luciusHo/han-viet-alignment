// Core of the review tool: pure functions on an array of pairs; no DOM, no network.
// pair = {id, doc, vi, vr, s, e, co, pv, dec, why, note, hanEdit, who, sec}; Han = H.slice(s, e); H never changes.
// Invariant (check): 0 <= s <= e <= H.length and e_i <= s_{i+1}; the unassigned Han is the gaps, so
// gaps + pairs concatenated in order == H (no Han lost or repeated).
const RC = (function () {
  const clone = (p, ch) => Object.assign({}, p, ch || {});
  const dirty = (p) => clone(p, { dec: "", hanEdit: null, mv: true, sug: null, hs: p.hs && p.hs.map((h) => (h.st === "a" ? Object.assign({}, h, { st: "" }) : h)) }); // a boundary move invalidates a Han edit and the decision

  function moveEnd(P, i, v) {
    const p = P[i], n = P[i + 1];
    const hi = n ? (n.e > n.s ? n.e - 1 : n.e) : Infinity, lo = p.e > p.s ? p.s + 1 : p.s; // never empty a non-empty pair
    v = Math.max(lo, Math.min(v, hi));
    if (v === p.e) return P;
    const Q = P.slice();
    Q[i] = dirty(clone(p, { e: v }));
    if (n && (n.s < v || n.s === p.e)) Q[i + 1] = dirty(clone(n, { s: v }));
    return Q;
  }
  function moveStart(P, i, v) {
    const p = P[i], q = P[i - 1];
    const lo = q ? (q.e > q.s ? q.s + 1 : q.s) : 0, hi = p.e > p.s ? p.e - 1 : p.e;
    v = Math.min(hi, Math.max(v, lo));
    if (v === p.s) return P;
    const Q = P.slice();
    Q[i] = dirty(clone(p, { s: v }));
    if (q && (q.e > v || q.e === p.s)) Q[i - 1] = dirty(clone(q, { e: v }));
    return Q;
  }
  const atWordStart = (t, k) => k > 0 && k < t.length && /\s/.test(t[k - 1]) && !/\s/.test(t[k]);
  const wordStart = (t, k) => { while (k > 0 && !/\s/.test(t[k - 1])) k--; return k; };
  const unassigned = (P, H) => { let n = 0, pos = 0; for (const p of P) { n += p.s - pos; pos = p.e; } return n + H.length - pos; };
  // split pair i: Viet at character index vpos, Han at offset cut (s <= cut <= e)
  function split(P, i, vpos, cut) {
    const p = P[i];
    if (!atWordStart(p.vi, vpos)) return P;
    if (p.e > p.s && (cut <= p.s || cut >= p.e)) return P;
    const a = p.vi.slice(0, vpos).trim(), b = p.vi.slice(vpos).trim();
    if (!a || !b || cut < p.s || cut > p.e) return P;
    const Q = P.slice();
    const base = { dec: "", hanEdit: null, why: "", note: p.note, sec: 0, sug: null };
    Q.splice(i, 1, clone(p, Object.assign({ vi: a, vr: a, e: cut, id: p.id + "a" }, base)),
      clone(p, Object.assign({ vi: b, vr: b, s: cut, id: p.id + "b", co: (p.co ? p.co + "," : "") + "tach" }, base)));
    return Q;
  }
  function merge(P, i) {
    const a = P[i], b = P[i + 1];
    if (!b) return P;
    const Q = P.slice();
    Q.splice(i, 2, clone(a, { vi: a.vi + " " + b.vi, vr: a.vr + " " + b.vr, e: b.e, dec: "", hanEdit: null, sug: null, why: "", vs: (a.vs || []).concat(b.vs || []), hs: (a.hs || []).concat(b.hs || []),
      note: [a.note, b.note].filter(Boolean).join("; "), co: (a.co ? a.co + "," : "") + "gop" }));
    return Q;
  }
  function check(P, H) {
    let last = 0;
    for (const p of P) {
      if (!(p.s >= last && p.s <= p.e && p.e <= H.length)) return false;
      last = p.e;
    }
    // reconstruct: gap + pair han ... + tail gap must equal H
    let out = "", pos = 0;
    for (const p of P) { out += H.slice(pos, p.s) + H.slice(p.s, p.e); pos = p.e; }
    return out + H.slice(pos) === H;
  }
  const hanOf = (H, p) => (p.hanEdit != null ? p.hanEdit : H.slice(p.s, p.e));
  const clean = (t) => String(t == null ? "" : t).replace(/[\t\r\n]+/g, " ");
  const COLS = ["stt", "doc_id", "trang", "viet_tho", "viet_sach", "han_tho", "han_sach", "quyet_dinh", "nguoi_ra", "giay", "ghi_chu", "x", "y", "id"];
  function pageAt(pages, off) { // pages: [[startOffset, page]] ascending
    let r = "";
    for (const [o, pg] of pages) { if (o <= off) r = pg; else break; }
    return r;
  }
  function toTsv(P, H, pages) {
    const rows = [COLS.join("\t")];
    P.forEach((p, k) => {
      const hp = p.e > p.s ? pageAt(pages, p.s) : "";
      rows.push([k + 1, p.doc, "V" + p.pv + "/H" + hp, clean(p.vr), clean(p.vi), H.slice(p.s, p.e), clean(hanOf(H, p)), p.dec,
        clean(p.who), p.sec || 0, clean([p.why, p.note].filter(Boolean).join("; ")), p.s, p.e, p.id].join("\t"));
    });
    let pos = 0, g = 0; // unassigned Han kept as 'khe' rows (after the pairs, ordered by x) so nothing is silently dropped
    const gaps = [];
    for (const p of P.concat([{ s: H.length, e: H.length }])) { if (p.s > pos) gaps.push([pos, p.s]); pos = p.e; }
    for (const [a, b] of gaps) rows.push([P.length + (++g), "", "", "", "", H.slice(a, b), H.slice(a, b), "khe", "", 0, "chu Han chua gan vao cap", a, b, "khe" + g].join("\t"));
    return rows.join("\n") + "\n";
  }
  // import an exported TSV: replaces the current pairs lying inside [min x, max y) of the file by the file's rows.
  function fromTsv(text, P, H) {
    const lines = text.replace(/\r/g, "").split("\n").filter(Boolean);
    const head = lines[0].split("\t");
    if (COLS.some((c, k) => head[k] !== c)) throw new Error("tieu de cot khong khop");
    const rows = lines.slice(1).map((l) => l.split("\t")).filter((c) => c[7] !== "khe");
    const R = rows.map((c) => ({ doc: c[1], pv: (c[2].match(/^V([^/]*)/) || [, ""])[1], vr: c[3], vi: c[4], han: c[5], hanS: c[6], dec: c[7],
      who: c[8], sec: +c[9] || 0, nt: c[10], s: +c[11], e: +c[12], id: c[13] }));
    for (const r of R) if (H.slice(r.s, r.e) !== r.han) throw new Error("chuoi Han khong khop (sai tap?) tai " + r.id);
    if (!R.length) return P;
    const lo = Math.min(...R.map((r) => r.s)), hi = Math.max(...R.map((r) => r.e));
    const keepBefore = P.filter((p) => p.e <= lo);
    const keepAfter = P.filter((p) => p.s >= hi);
    const mid = R.map((r) => ({ id: r.id, doc: r.doc, vi: r.vi, vr: r.vr, s: r.s, e: r.e, co: "", pv: r.pv, dec: r.dec, why: "", note: r.nt,
      hanEdit: r.hanS !== r.han ? r.hanS : null, who: r.who, sec: r.sec }));
    const Q = keepBefore.concat(mid, keepAfter);
    if (!check(Q, H)) throw new Error("ket qua gop khong bao toan chu Han");
    return Q;
  }
  return { atWordStart, wordStart, unassigned, moveEnd, moveStart, split, merge, check, toTsv, fromTsv, hanOf, pageAt, COLS };
})();
if (typeof module !== "undefined") module.exports = RC;
