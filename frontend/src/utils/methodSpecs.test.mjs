// 四字段（cost_band / timeline / advantages / limitations）前端映射的单元测试。
// Node 内置 node:test，跑法：node --test frontend/src/utils/methodSpecs.test.mjs
//
// 锁住三件事，都是实测踩过或极易踩的坑：
//   1. 枚举值必须映射成可读标签 —— 原实现是裸值直出，客户会看到 `low`、`hours`
//   2. 未知值必须原样返回 —— 人工可能填了自由文本，不能显示成 undefined/空
//   3. 单行数据按分号拆，不能按句号拆 —— 否则 `e.g.` 会被劈成两半

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  COST_BAND_LABELS,
  TIMELINE_LABELS,
  costBandLabel,
  timelineLabel,
  costBandShort,
  timelineShort,
  splitSpecLines,
} from './methodSpecs.js';

// ---------------------------------------------------------------------------
// 枚举映射：必须与 backend/apps/knowledge/models.py:180-191 的 choices 对齐

test('cost_band 三档全部有标签，与后端 choices 一致', () => {
  assert.deepEqual(Object.keys(COST_BAND_LABELS).sort(), ['high', 'low', 'medium']);
  assert.equal(costBandLabel('low'), 'Low (<$50/sample)');
  assert.equal(costBandLabel('medium'), 'Medium ($50–200/sample)');
  assert.equal(costBandLabel('high'), 'High (>$200/sample)');
});

test('timeline 四档全部有标签，与后端 choices 一致', () => {
  assert.deepEqual(
    Object.keys(TIMELINE_LABELS).sort(),
    ['days', 'hours', 'minutes', 'weeks'],
  );
  assert.equal(timelineLabel('minutes'), 'Minutes (<30 min)');
  assert.equal(timelineLabel('weeks'), 'Weeks (>1 week)');
});

test('空值返回空串，让模板的 v-if 直接生效', () => {
  assert.equal(costBandLabel(''), '');
  assert.equal(costBandLabel(null), '');
  assert.equal(costBandLabel(undefined), '');
  assert.equal(timelineLabel(''), '');
  assert.equal(timelineLabel(null), '');
});

test('未知值原样返回 —— 人工填的自由文本不能被吞掉', () => {
  assert.equal(costBandLabel('unknown'), 'unknown');
  assert.equal(timelineLabel('2 days'), '2 days');
});

test('卡片用短标签，不出现美元符号与括号', () => {
  assert.equal(costBandShort('low'), 'Low cost');
  assert.equal(costBandShort('high'), 'High cost');
  assert.equal(timelineShort('minutes'), '<30 min');
  assert.equal(timelineShort('days'), '1–7 d');
  assert.ok(!costBandShort('medium').includes('$'));
});

// ---------------------------------------------------------------------------
// 行拆分：模型 help_text 要求「每条一行」

test('多行文本按行拆分', () => {
  const out = splitSpecLines('High specificity\nWorks on live cells\nFast turnaround');
  assert.deepEqual(out, ['High specificity', 'Works on live cells', 'Fast turnaround']);
});

test('单行文本按分号拆分（历史人工录入的形态）', () => {
  const out = splitSpecLines('High specificity；Works on live cells; Fast turnaround');
  assert.deepEqual(out, ['High specificity', 'Works on live cells', 'Fast turnaround']);
});

test('不按句号拆 —— e.g. / i.e. 不能被劈开', () => {
  const out = splitSpecLines('Works on most samples, e.g. blood and tissue');
  assert.deepEqual(out, ['Works on most samples, e.g. blood and tissue']);
});

test('去掉行首项目符号与行尾标点', () => {
  assert.deepEqual(splitSpecLines('- item one\n• item two\n* item three'), [
    'item one',
    'item two',
    'item three',
  ]);
  assert.deepEqual(splitSpecLines('one;two.'), ['one', 'two']);
});

test('空输入返回空数组，不产生空字符串项', () => {
  assert.deepEqual(splitSpecLines(''), []);
  assert.deepEqual(splitSpecLines(null), []);
  assert.deepEqual(splitSpecLines('   '), []);
  assert.deepEqual(splitSpecLines('\n\n'), []);
});
