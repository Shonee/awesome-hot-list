import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const html = readFileSync(new URL('../src/template/site.html', import.meta.url), 'utf8');
const source = html.slice(html.indexOf('  <script>') + '  <script>'.length, html.indexOf('  </script>'));
const context = vm.createContext({ URL, window: { location: { href: 'https://example.com/' } } });

function loadFunctions(start, end) {
  vm.runInContext(source.slice(source.indexOf(`    function ${start}(`), source.indexOf(`    function ${end}(`)), context);
}

loadFunctions('splitRankSegments', 'renderSignals');
loadFunctions('groupHits', 'openTopic');
loadFunctions('openTopic', 'bindTopicButtons');
loadFunctions('safeUrl', 'rankMovementValue');

test('unranked samples use a dashed baseline and transitions without invented rank points', () => {
  const { rankPlotPaths } = context;
  const xAt = index => 4 + index * 46;
  const yAt = rank => 12 + (rank - 1) * 2;
  const rising = rankPlotPaths([null, null, 10], xAt, yAt);
  assert.equal(rising.solid.length, 0);
  assert.equal(rising.missing.length, 2);
  assert.equal(rising.points.filter(Boolean).length, 1);
  assert.equal(rising.points[0], null);
  assert.match(rising.missing[0], /M 4 94 L 50 94/);
  assert.match(rising.missing[1], /L 96 30/);

  const returned = rankPlotPaths([2, null, 3], xAt, yAt);
  assert.equal(returned.solid.length, 0);
  assert.equal(returned.missing.length, 2);
  assert.equal(returned.points.filter(Boolean).length, 2);
  assert.equal(rankPlotPaths([2], () => 50, yAt).missing.length, 0);
  assert.equal(rankPlotPaths([2, 3], xAt, yAt).solid.length, 1);
});

test('legacy report hits group the same event while retaining distinct source links', () => {
  const { groupHits } = context;
  const groups = groupHits([
    { channelId: 'weibo', title: '男子30年前存一万定期忘取', url: 'https://example.com/a', rank: 1 },
    { channelId: 'kuaishou', title: '男子30年前存一万定期忘取', url: 'https://example.com/b', rank: 4 },
    { channelId: 'baidu', title: '男子30年前存一万定期忘取法院判了', url: 'https://example.com/c', rank: 8 },
    { channelId: 'weibo', title: '另一条完全不同的事件', url: 'https://example.com/d', rank: 3 },
  ]);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].sources.length, 3);
  assert.equal(groups[1].sources.length, 1);
});

test('the chart renders missing intervals and the dialog shows one title with three links', () => {
  const elements = new Map();
  context.document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '', showModal() {} });
      return elements.get(id);
    },
  };
  context.escapeHtml = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;');
  context.bindTopicButtons = () => {};
  context.CHANNELS = {};
  context.TOPIC_LABELS = {};
  context.relatedItems = () => [
    { channel: 'weibo', title: '男子30年前存一万定期忘取', url: 'https://example.com/a' },
    { channel: 'kuaishou', title: '男子30年前存一万定期忘取', url: 'https://example.com/b' },
    { channel: 'baidu', title: '男子30年前存一万定期忘取法院判了', url: 'https://example.com/c' },
  ];
  context.renderRankFlow('chart', { times: ['09:00', '10:00', '11:00'], rows: [{
    topic: '新热点', query: 'new', ranks: [null, null, 10],
    source: '哔哩哔哩', ranking: '视频排行', tenure: '1/3 个切片', tone: 'new', state: '新上榜',
  }] });
  assert.equal((elements.get('chart').innerHTML.match(/class="rank-absence"/g) || []).length, 2);
  assert.equal((elements.get('chart').innerHTML.match(/class="rank-point /g) || []).length, 1);
  assert.match(elements.get('chart').innerHTML, /09:00未上榜/);
  context.openTopic('topic');
  assert.match(elements.get('topicDialogTitle').textContent, /1 条关联内容/);
  assert.equal((elements.get('topicDialogBody').innerHTML.match(/class="topic-result-title"/g) || []).length, 1);
  assert.equal((elements.get('topicDialogBody').innerHTML.match(/class="topic-source"/g) || []).length, 3);
});

test('one deduplicated destination opens directly', () => {
  const opened = [];
  context.window.open = (...args) => opened.push(args);
  context.relatedItems = () => [
    { channel: 'weibo', title: '同一件事的新闻标题', url: 'https://example.com/one' },
    { channel: 'weibo', title: '同一件事的新闻标题', url: 'https://example.com/one?rank=2' },
  ];
  context.openTopic('same');
  assert.equal(opened.length, 1);
  assert.equal(opened[0][0], 'https://example.com/one');
});
