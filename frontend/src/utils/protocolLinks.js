// protocolLinks.js — pure helpers for the Product Edit page "Knowledge Links"
// -> Protocols section (#356). No Vue dependency so it is unit-testable with
// Node's built-in node:test (see protocolLinks.test.mjs).
//
// Contract mirrors backend get_protocol_links (backend serializers.py #355):
//   row = {id,name,slug,relevance_score,score_a,score_b,score_c,
//          relevance_basis,link_source,tier}
//   sort key = (TIER_RANK[tier] asc, -relevance desc, -score_c desc, id asc)
//   S4: 'weak'（弱相关/仅语义相似/广播桶）TIER_RANK 最高 → 恒沉底。
//
// Three iron laws honored:
//   ① maximize data — fold NEVER deletes; every derived link is kept.
//   ② strongest relevance — sort puts evidenced tiers on top & is attributable.
//   ③ editorial denoise via sort/fold/labels, never by dropping links.

export const TIER_RANK = { literature: 0, document: 1, featured: 2, weak: 3 };

export const TIER_LABEL = {
  literature: '文献支持',
  document: '文档相关',
  featured: '编辑精选',
  weak: '仅语义相似',
};

export const LINK_SOURCE_LABEL = {
  explicit: '显式关联',
  inherited: '派生关联',
  auto: '自动匹配',
  // Transient (frontend-only) state for ids added by "AI auto match → save"
  // that have not yet been persisted to the DB via Save. Once the product form
  // is saved and the page reloaded, these ids become real ProductMethod /
  // ProductProtocol rows with link_source='auto'/'inherited'/'explicit'.
  queued: '待保存',
};

// Round a 0..1 score to 2 decimals for display ("0.85"), keeping the raw
// numeric field intact on the row (display-only formatting).
function formatScore(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return null;
  return (Math.round(Number(n) * 100) / 100).toFixed(2);
}

// Normalize a raw protocol_link row from the server into a display-ready row.
// Applies defaults matching backend get_protocol_links fallback semantics
// (tier='weak' [S4], relevance_score=0, link_source='inherited',
// literature_count=0) and attaches Chinese labels. Does NOT mutate input.
export function enrichProtocolRow(row) {
  const r = { ...row };
  if (r.tier === undefined || r.tier === null) r.tier = 'weak';
  if (r.relevance_score === undefined || r.relevance_score === null) r.relevance_score = 0.0;
  if (r.score_a === undefined) r.score_a = null;
  if (r.score_b === undefined) r.score_b = null;
  if (r.score_c === undefined) r.score_c = null;
  if (r.relevance_basis === undefined || r.relevance_basis === null) r.relevance_basis = '';
  if (r.link_source === undefined || r.link_source === null) r.link_source = 'inherited';
  if (r.literature_count === undefined || r.literature_count === null) r.literature_count = 0;

  r.tier_label = TIER_LABEL[r.tier] || '';
  r.link_source_label = LINK_SOURCE_LABEL[r.link_source] || '—';
  return r;
}

// Sort protocol_link rows by (tier rank asc, relevance desc, score_c desc,
// id asc). Returns a NEW array; original is untouched.
export function sortProtocolLinks(rows) {
  return [...rows].sort((a, b) => {
    const rankA = TIER_RANK[a.tier] ?? 2;
    const rankB = TIER_RANK[b.tier] ?? 2;
    if (rankA !== rankB) return rankA - rankB;
    const relA = Number(a.relevance_score) || 0;
    const relB = Number(b.relevance_score) || 0;
    if (relA !== relB) return relB - relA;
    const scA = Number(a.score_c) || 0;
    const scB = Number(b.score_c) || 0;
    if (scA !== scB) return scB - scA;
    return Number(a.id) - Number(b.id);
  });
}

// Display-layer TopN folding. Fold != delete: ALL rows are preserved across
// `visible` + `hidden`. When showAll is true (user clicked "显示全部(M)"),
// everything is visible and nothing is hidden.
export function buildFolded(rows, topN = 10, showAll = false) {
  if (showAll) {
    return { visible: [...rows], hidden: [], folded: false };
  }
  const visible = rows.slice(0, topN);
  const hidden = rows.slice(topN);
  return { visible, hidden, folded: rows.length > topN };
}

// S4: 把 weak（弱相关/广播桶）行从强相关行中分离，供 UI 折叠为
// "弱相关(N)" 折叠区。铁律③：折叠≠删除——strong/weak 都完整保留，
// 调用方负责把 weak 默认收起、点击展开。返回 {strong, weak}。
export function splitWeakLinks(rows) {
  const strong = [];
  const weak = [];
  for (const r of rows || []) {
    if (r.tier === 'weak') weak.push(r);
    else strong.push(r);
  }
  return { strong, weak };
}

// Three-axis badges for a (enriched) row.
//   Axis A: F=0.xx  (vendor/docx claimed relevance, score_a)
//   Axis B: 文献×N  (per-protocol Bioz-aligned count, literature_count>0 only)
//   Axis C: C=0.xx  (embedding precomputed score, score_c)
//   Tier marker (仅语义相似/编辑精选/文献支持/文档相关) shown by default.
// Returns array of {axis, text, kind} for styling. Display-only.
export function axisBadges(row, { includeTier = true } = {}) {
  const badges = [];
  const f = formatScore(row.score_a);
  if (f !== null) badges.push({ axis: 'A', text: `F=${f}`, kind: 'axis-a' });

  const lit = Number(row.literature_count) || 0;
  if (lit > 0) badges.push({ axis: 'B', text: `文献×${lit}`, kind: 'axis-b' });

  const c = formatScore(row.score_c);
  if (c !== null) badges.push({ axis: 'C', text: `C=${c}`, kind: 'axis-c' });

  if (includeTier && TIER_LABEL[row.tier]) {
    badges.push({ axis: 'tier', text: TIER_LABEL[row.tier], kind: `tier-${row.tier}` });
  }
  return badges;
}

// Human-readable label for a link_source enum; dash for unknown/empty.
export function sourceChip(src) {
  return LINK_SOURCE_LABEL[src] ?? '—';
}

// Union authoritative server-derived protocol_link rows (productProtocolLinks)
// with locally-added protocolIds that have not yet been through recompute.
// Iron law ①: NEVER drop a link — every server row AND every local id is kept.
//   - a local id already present in server rows is deduped (not duplicated)
//   - local-only ids get fallback defaults mirroring the serializer fallback
//     branch (tier='featured', link_source='inherited', relevance_score=0) and a
//     display name resolved via nameLookup(pid)
//   - server row values are preserved (no default overwrite)
//   - non-mutating on inputs; sort/fold is done by the caller (sortProtocolLinks
//     + buildFolded)
export function unionProtocolRows(serverRows = [], localIds = [], nameLookup = null) {
  const rows = [];
  const seen = new Set();
  for (const r of serverRows || []) {
    if (r && r.id !== undefined && r.id !== null) {
      rows.push(enrichProtocolRow(r));
      seen.add(r.id);
    }
  }
  const lookup = typeof nameLookup === 'function' ? nameLookup : () => null;
  for (const pid of localIds || []) {
    if (seen.has(pid)) continue;
    rows.push(enrichProtocolRow({
      id: pid,
      name: lookup(pid),
      tier: 'weak',
      // 'queued' (not 'inherited') so the source badge honestly reflects
      // "not yet persisted" — the Save action will turn these into real
      // ProductMethod / ProductProtocol rows.
      link_source: 'queued',
      relevance_score: 0,
    }));
    seen.add(pid);
  }
  return rows;
}

export default {
  TIER_RANK,
  TIER_LABEL,
  LINK_SOURCE_LABEL,
  enrichProtocolRow,
  sortProtocolLinks,
  buildFolded,
  splitWeakLinks,
  axisBadges,
  sourceChip,
  unionProtocolRows,
};
