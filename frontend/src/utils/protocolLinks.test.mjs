// RED phase (#367) — TDD for src/utils/protocolLinks.js
// Pure-function unit tests using Node 22 built-in node:test (framework-agnostic).
// These MUST fail until protocolLinks.js is implemented (#368 GREEN).
//
// Contract mirrors backend get_protocol_links (serializers.py #355):
//   row = {id,name,slug,relevance_score,score_a,score_b,score_c,
//          relevance_basis,link_source,tier}
//   sort key = (TIER_RANK[tier] asc, -relevance desc, -score_c desc, id asc)
// Three iron laws honored: fold != delete (keep all), no product-level
// count masquerading as protocol-level (literature_count is per-protocol),
// never drop links at data layer.

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
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
} from './protocolLinks.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
test('TIER_RANK: literature > document > featured (ascending priority)', () => {
  assert.equal(TIER_RANK.literature, 0);
  assert.equal(TIER_RANK.document, 1);
  assert.equal(TIER_RANK.featured, 2);
  // unknown tier falls back to 2 (featured) on sort
});

test('TIER_LABEL maps enum -> Chinese', () => {
  assert.equal(TIER_LABEL.literature, '文献支持');
  assert.equal(TIER_LABEL.document, '文档相关');
  assert.equal(TIER_LABEL.featured, '编辑精选');
});

test('LINK_SOURCE_LABEL maps enum -> Chinese', () => {
  assert.equal(LINK_SOURCE_LABEL.explicit, '显式关联');
  assert.equal(LINK_SOURCE_LABEL.inherited, '派生关联');
  assert.equal(LINK_SOURCE_LABEL.auto, '自动匹配');
  assert.equal(LINK_SOURCE_LABEL.queued, '待保存');
});

// ---------------------------------------------------------------------------
// enrichProtocolRow
// ---------------------------------------------------------------------------
test('enrichProtocolRow fills defaults without mutating input', () => {
  const input = { id: 1, name: 'Proto A' };
  const out = enrichProtocolRow(input);

  // does not mutate
  assert.equal(input.tier, undefined);
  // defaults applied (S4: tier 默认 weak 而非 featured)
  assert.equal(out.tier, 'weak');
  assert.equal(out.relevance_score, 0.0);
  assert.equal(out.score_a, null);
  assert.equal(out.score_b, null);
  assert.equal(out.score_c, null);
  assert.equal(out.relevance_basis, '');
  assert.equal(out.link_source, 'inherited');
  assert.equal(out.literature_count, 0);
  // labels attached
  assert.equal(out.tier_label, '仅语义相似');
  assert.equal(out.link_source_label, '派生关联');
  // keeps original fields
  assert.equal(out.name, 'Proto A');
});

test('enrichProtocolRow preserves provided values and rounds score_a/c', () => {
  const input = {
    id: 7,
    name: 'Proto B',
    slug: 'proto-b',
    relevance_score: 0.42,
    score_a: 0.853,
    score_b: 0.3,
    score_c: 0.777,
    relevance_basis: 'bioz_aligned',
    link_source: 'explicit',
    tier: 'literature',
    literature_count: 5,
  };
  const out = enrichProtocolRow(input);
  assert.equal(out.tier, 'literature');
  assert.equal(out.tier_label, '文献支持');
  assert.equal(out.link_source, 'explicit');
  assert.equal(out.link_source_label, '显式关联');
  assert.equal(out.relevance_score, 0.42);
  assert.equal(out.score_a, 0.853);
  assert.equal(out.score_c, 0.777);
  assert.equal(out.literature_count, 5);
});

// ---------------------------------------------------------------------------
// sortProtocolLinks
// ---------------------------------------------------------------------------
test('sortProtocolLinks orders by tier, then relevance desc, then score_c desc, then id asc', () => {
  const rows = [
    { id: 1, tier: 'featured', relevance_score: 0.9, score_c: 0.1 },
    { id: 2, tier: 'literature', relevance_score: 0.5, score_c: 0.1 },
    { id: 3, tier: 'document', relevance_score: 0.9, score_c: 0.1 },
    { id: 4, tier: 'literature', relevance_score: 0.5, score_c: 0.9 },
    { id: 5, tier: 'literature', relevance_score: 0.7, score_c: 0.1 },
  ];
  const sorted = sortProtocolLinks(rows);
  const ids = sorted.map((r) => r.id);
  // literature(5,4,2) -> document(3) -> featured(1)
  assert.deepEqual(ids, [5, 4, 2, 3, 1]);
});

test('sortProtocolLinks is non-mutating and returns a new array', () => {
  const rows = [
    { id: 9, tier: 'featured', relevance_score: 0.1 },
    { id: 8, tier: 'featured', relevance_score: 0.9 },
  ];
  const sorted = sortProtocolLinks(rows);
  assert.notEqual(sorted, rows); // different reference
  assert.deepEqual(rows.map((r) => r.id), [9, 8]); // original untouched
  assert.deepEqual(sorted.map((r) => r.id), [8, 9]);
});

test('sortProtocolLinks treats missing tier as featured (rank 2)', () => {
  const rows = [
    { id: 1, tier: 'document', relevance_score: 0.5 },
    { id: 2, tier: undefined, relevance_score: 0.9 }, // -> featured
  ];
  const ids = sortProtocolLinks(rows).map((r) => r.id);
  assert.deepEqual(ids, [1, 2]); // document before featured
});

// ---------------------------------------------------------------------------
// buildFolded  (fold != delete)
// ---------------------------------------------------------------------------
test('buildFolded keeps all rows when under topN', () => {
  const rows = Array.from({ length: 8 }, (_, i) => ({ id: i + 1 }));
  const { visible, hidden, folded } = buildFolded(rows, 10);
  assert.equal(folded, false);
  assert.equal(visible.length, 8);
  assert.equal(hidden.length, 0);
  assert.equal(visible.length + hidden.length, rows.length);
});

test('buildFolded folds overflow beyond topN but preserves every row', () => {
  const rows = Array.from({ length: 12 }, (_, i) => ({ id: i + 1 }));
  const { visible, hidden, folded } = buildFolded(rows, 10);
  assert.equal(folded, true);
  assert.equal(visible.length, 10);
  assert.equal(hidden.length, 2);
  // nothing lost
  assert.equal(visible.length + hidden.length, 12);
  const allIds = [...visible, ...hidden].map((r) => r.id).sort((a, b) => a - b);
  assert.deepEqual(allIds, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
});

test('buildFolded honours custom topN', () => {
  const rows = Array.from({ length: 7 }, (_, i) => ({ id: i + 1 }));
  const { visible, hidden, folded } = buildFolded(rows, 5);
  assert.equal(folded, true);
  assert.equal(visible.length, 5);
  assert.equal(hidden.length, 2);
});

test('buildFolded showAll renders everything (no fold)', () => {
  const rows = Array.from({ length: 20 }, (_, i) => ({ id: i + 1 }));
  const { visible, hidden, folded } = buildFolded(rows, 10, true);
  assert.equal(folded, false);
  assert.equal(visible.length, 20);
  assert.equal(hidden.length, 0);
});

test('buildFolded hidden rows retain original data (fold is display-only)', () => {
  const rows = [
    { id: 1, name: 'keep-me', tier: 'literature', relevance_score: 0.9 },
    { id: 2, name: 'also-keep', tier: 'featured', relevance_score: 0.1 },
  ];
  const { hidden } = buildFolded(rows, 1);
  assert.equal(hidden.length, 1);
  assert.equal(hidden[0].name, 'also-keep');
  assert.equal(hidden[0].tier, 'featured');
});

// ---------------------------------------------------------------------------
// axisBadges (three-axis: F=score_a / 文献×N / C=score_c + tier marker)
// ---------------------------------------------------------------------------
test('axisBadges renders F, 文献×N, C and tier for a fully-scored featured row', () => {
  const row = enrichProtocolRow({
    id: 1,
    score_a: 0.853,
    score_c: 0.42,
    literature_count: 3,
    tier: 'featured',
  });
  const badges = axisBadges(row);
  const texts = badges.map((b) => b.text);
  assert.ok(texts.includes('F=0.85'), `expected F=0.85, got ${JSON.stringify(texts)}`);
  assert.ok(texts.includes('文献×3'), `expected 文献×3, got ${JSON.stringify(texts)}`);
  assert.ok(texts.includes('C=0.42'), `expected C=0.42, got ${JSON.stringify(texts)}`);
  assert.ok(texts.includes('编辑精选'), `expected 编辑精选 tier, got ${JSON.stringify(texts)}`);
  // each badge carries axis + kind for styling
  const f = badges.find((b) => b.text.startsWith('F='));
  assert.equal(f.axis, 'A');
  assert.equal(f.kind, 'axis-a');
});

test('axisBadges omits F when score_a is null', () => {
  const row = enrichProtocolRow({ id: 1, score_a: null, literature_count: 0, tier: 'document' });
  const badges = axisBadges(row);
  assert.ok(!badges.some((b) => b.text.startsWith('F=')), 'F badge should be absent');
  const texts = badges.map((b) => b.text);
  assert.ok(texts.includes('文档相关'), 'tier badge should still appear');
});

test('axisBadges omits 文献×N when literature_count is 0', () => {
  const row = enrichProtocolRow({ id: 1, score_a: 0.5, literature_count: 0, tier: 'literature' });
  const badges = axisBadges(row);
  assert.ok(!badges.some((b) => b.text.startsWith('文献×')), '文献 badge should be absent');
});

test('axisBadges includeTier=false suppresses tier marker', () => {
  const row = enrichProtocolRow({ id: 1, score_a: 0.5, literature_count: 2, tier: 'featured' });
  const badges = axisBadges(row, { includeTier: false });
  assert.ok(!badges.some((b) => b.text === '编辑精选'), 'tier badge suppressed');
  assert.ok(badges.some((b) => b.text.startsWith('F=')));
  assert.ok(badges.some((b) => b.text.startsWith('文献×')));
});

// ---------------------------------------------------------------------------
// sourceChip (link_source -> label, unknown -> dash)
// ---------------------------------------------------------------------------
test('sourceChip maps known link_source enum', () => {
  assert.equal(sourceChip('explicit'), '显式关联');
  assert.equal(sourceChip('inherited'), '派生关联');
  assert.equal(sourceChip('auto'), '自动匹配');
  assert.equal(sourceChip('queued'), '待保存');
});

test('sourceChip returns dash for empty/unknown source', () => {
  assert.equal(sourceChip(''), '—');
  assert.equal(sourceChip(undefined), '—');
  assert.equal(sourceChip('mystery'), '—');
});

// ---------------------------------------------------------------------------
// S4 · tier 语义修正 + 广播沉底 (weak)
// ---------------------------------------------------------------------------
test('TIER_LABEL.weak maps to 仅语义相似 (honest badge, not 编辑精选)', () => {
  assert.equal(TIER_LABEL.weak, '仅语义相似');
});

test('TIER_RANK.weak sinks below all other tiers (highest rank)', () => {
  assert.equal(TIER_RANK.weak, 3);
  assert.ok(TIER_RANK.weak > TIER_RANK.featured);
  assert.ok(TIER_RANK.weak > TIER_RANK.document);
  assert.ok(TIER_RANK.weak > TIER_RANK.literature);
});

test('sortProtocolLinks sinks weak below higher-relevance non-weak rows', () => {
  // weak 即便 relevance 更高，也恒沉底
  const rows = [
    { id: 1, tier: 'weak', relevance_score: 0.99, score_c: 0.9 },
    { id: 2, tier: 'document', relevance_score: 0.30, score_c: 0.2 },
  ];
  const ids = sortProtocolLinks(rows).map((r) => r.id);
  assert.deepEqual(ids, [2, 1]); // document 在上，weak 沉底
});

test('sortProtocolLinks weak internal still by relevance desc', () => {
  const rows = [
    { id: 1, tier: 'weak', relevance_score: 0.9, score_c: 0.1 },
    { id: 2, tier: 'weak', relevance_score: 0.3, score_c: 0.2 },
  ];
  assert.deepEqual(sortProtocolLinks(rows).map((r) => r.id), [1, 2]);
});

test('enrichProtocolRow missing tier defaults to weak (S4)', () => {
  const out = enrichProtocolRow({ id: 5, name: 'Proto' });
  assert.equal(out.tier, 'weak');
  assert.equal(out.tier_label, '仅语义相似');
});

test('unionProtocolRows local-only ids default to weak tier (S4)', () => {
  const rows = unionProtocolRows([], [42], (pid) => (pid === 42 ? 'Local' : null));
  assert.equal(rows.length, 1);
  assert.equal(rows[0].tier, 'weak');
  assert.equal(rows[0].link_source, 'queued');
});

test('splitWeakLinks separates weak from strong without dropping either', () => {
  const rows = [
    { id: 1, tier: 'document', relevance_score: 0.6 },
    { id: 2, tier: 'weak', relevance_score: 0.99 },
    { id: 3, tier: 'literature', relevance_score: 0.4 },
    { id: 4, tier: 'weak', relevance_score: 0.3 },
  ];
  const { strong, weak } = splitWeakLinks(rows);
  assert.deepEqual(strong.map((r) => r.id), [1, 3]);
  assert.deepEqual(weak.map((r) => r.id), [2, 4]);
  assert.equal(strong.length + weak.length, rows.length); // 零删除
});
