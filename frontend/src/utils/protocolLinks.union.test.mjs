// RED phase (#357) — TDD for unionProtocolRows in src/utils/protocolLinks.js.
// Extracted from ProductEditPage.vue displayProtocolRows inline union logic.
//
// unionProtocolRows(serverRows, localIds, nameLookup) must:
//   - keep EVERY server row (iron law ①: never drop a derived link)
//   - keep EVERY local id not already present in server rows
//   - dedup: a local id already in server rows is NOT duplicated
//   - for local-only ids, apply defaults {tier:'featured', link_source:'queued',
//     relevance_score:0} and resolve name via nameLookup(pid)
//   - preserve server row values (do NOT overwrite with defaults)
//   - be non-mutating on inputs
//
// Local-only 'queued' label is a transient frontend state meaning
// "added by AI auto match → save but not yet saved to the DB" —
// the Save Product action will turn these into real ProductMethod /
// ProductProtocol rows. Showing them as 'inherited' was misleading.
//
// These MUST fail (ERR_MODULE_NOT_FOUND) until protocolLinks.js exports
// unionProtocolRows (#374 GREEN).

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { unionProtocolRows } from './protocolLinks.js';

const nameLookup = (pid) => (pid === 9 ? 'Local Proto 9' : null);

test('unionProtocolRows keeps all server rows + all local ids (iron law ①)', () => {
  const server = [
    { id: 1, name: 'S1', tier: 'literature', relevance_score: 0.9 },
    { id: 2, name: 'S2', tier: 'document', relevance_score: 0.5 },
    { id: 3, name: 'S3', tier: 'featured', relevance_score: 0.0 },
  ];
  const local = [7, 8]; // not in server
  const rows = unionProtocolRows(server, local, nameLookup);
  const ids = rows.map((r) => r.id).sort((a, b) => a - b);
  assert.deepEqual(ids, [1, 2, 3, 7, 8]); // nothing dropped, nothing missed
});

test('unionProtocolRows dedups a local id already present in server rows', () => {
  const server = [{ id: 5, name: 'S5', tier: 'literature', relevance_score: 0.9 }];
  const local = [5, 6]; // 5 already in server -> must not duplicate
  const rows = unionProtocolRows(server, local, nameLookup);
  const fives = rows.filter((r) => r.id === 5);
  assert.equal(fives.length, 1, 'local id 5 must not be duplicated');
  const ids = rows.map((r) => r.id).sort((a, b) => a - b);
  assert.deepEqual(ids, [5, 6]);
});

test('unionProtocolRows applies featured/queued/0 defaults + name for local-only', () => {
  const server = [];
  const local = [9];
  const rows = unionProtocolRows(server, local, nameLookup);
  assert.equal(rows.length, 1);
  const r = rows[0];
  assert.equal(r.id, 9);
  assert.equal(r.name, 'Local Proto 9'); // from nameLookup
  assert.equal(r.tier, 'featured');
  // Queued (not inherited): honestly says "added by AI auto match, not yet persisted"
  assert.equal(r.link_source, 'queued');
  assert.equal(r.relevance_score, 0);
  assert.equal(r.tier_label, '编辑精选');
  assert.equal(r.link_source_label, '待保存');
});

test('unionProtocolRows renders server auto rows with real link_source (not downgraded to queued)', () => {
  // Server rows with link_source='auto' must pass through unchanged.
  // Local fallback to 'queued' must NEVER overwrite a real server row.
  const server = [
    { id: 1, name: 'Auto', link_source: 'auto', tier: 'document', relevance_score: 0.6 },
  ];
  const local = []; // empty
  const rows = unionProtocolRows(server, local, nameLookup);
  assert.equal(rows[0].link_source, 'auto');
  assert.equal(rows[0].link_source_label, '自动匹配');
});

test('unionProtocolRows preserves server row values (no default overwrite)', () => {
  const server = [{ id: 2, name: 'S2', tier: 'literature', relevance_score: 0.77, score_c: 0.4 }];
  const local = [];
  const rows = unionProtocolRows(server, local, nameLookup);
  assert.equal(rows.length, 1);
  const r = rows[0];
  assert.equal(r.tier, 'literature');
  assert.equal(r.tier_label, '文献支持');
  assert.equal(r.relevance_score, 0.77);
  assert.equal(r.score_c, 0.4);
});

test('unionProtocolRows is non-mutating on input arrays', () => {
  const server = [{ id: 1, name: 'S1', tier: 'featured', relevance_score: 0.1 }];
  const local = [2];
  const serverBefore = JSON.parse(JSON.stringify(server));
  const localBefore = [...local];
  unionProtocolRows(server, local, nameLookup);
  assert.deepEqual(server, serverBefore);
  assert.deepEqual(local, localBefore);
});

test('unionProtocolRows tolerates empty / missing inputs', () => {
  assert.deepEqual(unionProtocolRows([], [], nameLookup), []);
  assert.deepEqual(unionProtocolRows(undefined, undefined, nameLookup), []);
  // local-only with no lookup fn -> name null
  const rows = unionProtocolRows([], [4], undefined);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].id, 4);
  assert.equal(rows[0].name, null);
});
