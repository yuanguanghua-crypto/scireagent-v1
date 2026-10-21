# -*- coding: utf-8 -*-
"""外部数据源录制 / 回放（cassette）—— `core/http_cassette.py` 的契约测试

## 这组用例要钉住什么
1. **默认 off**：不设环境变量时行为与引入前完全一致（不能有任何副作用）
2. **key 稳定**：只由请求语义决定 —— query 顺序不同、params 用 dict 还是拼在 URL 里，
   都必须算出同一个 key（否则录制与回放两次算法输入不同 ⇒ 永远 miss）
3. **replay 绝不回源**：未命中必须抛 `CassetteMiss`。这是整个模块的安全底线 ——
   静默回源会让 CI 重新依赖外网，而且测试表面绿、实际走网络（假绿）
4. **不落敏感头**：cassette 是要进仓库的，`Authorization` / `Cookie` 绝对不能写进去
5. **大 body 整条跳过**：不存半截数据（"回放成功但内容残缺"比 miss 更危险）
6. **非法 MODE 显式报错**：静默回落 off 会让人以为在录制却什么都没录
"""
import base64
import json
import os
import tempfile
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from core import http_cassette
from core.datasource_client import request_with_resilience


def _fake_response(status=200, body=b'{"ok":true}', headers=None, encoding='utf-8', url=None):
    resp = requests.models.Response()
    resp.status_code = status
    resp.url = url or 'https://example.test/x'
    resp.encoding = encoding
    resp._content = body
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    resp.request = requests.Request('GET', resp.url).prepare()
    return resp


class _TempCassetteMixin:
    """每条用例用独立临时目录，互不干扰、也不污染仓库。"""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        patcher = mock.patch.dict(os.environ, {http_cassette.DIR_ENV: self.dir}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: os.environ.pop(http_cassette.MODE_ENV, None))

    def _set_mode(self, mode):
        os.environ[http_cassette.MODE_ENV] = mode

    def _read_lines(self, source):
        path = http_cassette.cassette_path(source)
        if not os.path.exists(path):
            return []
        with open(path, encoding='utf-8') as f:
            return [json.loads(x) for x in f if x.strip()]


class ModeResolutionTests(_TempCassetteMixin, SimpleTestCase):
    def test_default_is_off(self):
        os.environ.pop(http_cassette.MODE_ENV, None)
        self.assertEqual(http_cassette.http_mode(), http_cassette.MODE_OFF)

    def test_invalid_mode_raises(self):
        """非法值必须报错。静默回落 off 会让人以为在录制，实际一条都没录。"""
        self._set_mode('recrod')          # 故意拼错
        with self.assertRaises(ValueError):
            http_cassette.http_mode()


class KeyStabilityTests(SimpleTestCase):
    URL = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/property/MolecularFormula/JSON'

    def test_same_request_same_key(self):
        a = http_cassette.cassette_key('GET', self.URL)
        b = http_cassette.cassette_key('GET', self.URL)
        self.assertEqual(a, b)

    def test_method_is_case_insensitive(self):
        self.assertEqual(
            http_cassette.cassette_key('get', self.URL),
            http_cassette.cassette_key('GET', self.URL),
        )

    def test_query_order_irrelevant(self):
        """?a=1&b=2 与 ?b=2&a=1 必须是同一个 key —— 调用方拼参顺序不统一。"""
        u1 = self.URL + '?a=1&b=2'
        u2 = self.URL + '?b=2&a=1'
        self.assertEqual(
            http_cassette.cassette_key('GET', u1),
            http_cassette.cassette_key('GET', u2),
        )

    def test_params_dict_equals_encoded_query(self):
        """params={'a':'1'} 与 URL 里写 ?a=1 必须是同一个 key。

        这条最容易漏：requests 会把 params **追加**到 URL 的 query 上，
        若 key 只算 URL 而不算 params，录制（带 params）与回放（可能已拼进 URL）
        就会算出不同 key ⇒ 永远 miss。
        """
        self.assertEqual(
            http_cassette.cassette_key('GET', self.URL, params={'a': '1', 'b': '2'}),
            http_cassette.cassette_key('GET', self.URL + '?a=1&b=2'),
        )

    def test_different_path_different_key(self):
        self.assertNotEqual(
            http_cassette.cassette_key('GET', self.URL),
            http_cassette.cassette_key('GET', self.URL.replace('2244', '2245')),
        )

    def test_different_host_different_key(self):
        self.assertNotEqual(
            http_cassette.cassette_key('GET', 'https://a.test/x'),
            http_cassette.cassette_key('GET', 'https://b.test/x'),
        )

    def test_different_body_different_key(self):
        self.assertNotEqual(
            http_cassette.cassette_key('POST', self.URL, json={'q': 'a'}),
            http_cassette.cassette_key('POST', self.URL, json={'q': 'b'}),
        )

    def test_json_body_key_order_irrelevant(self):
        """JSON dict 的键顺序不该影响 key（否则同一 payload 两种写法就 miss）。"""
        self.assertEqual(
            http_cassette.cassette_key('POST', self.URL, json={'a': 1, 'b': 2}),
            http_cassette.cassette_key('POST', self.URL, json={'b': 2, 'a': 1}),
        )

    def test_headers_do_not_affect_key(self):
        """headers 含 UA / 时间戳 / 令牌，纳入 key 会让它永远不稳定。"""
        self.assertEqual(
            http_cassette.cassette_key('GET', self.URL),
            http_cassette.cassette_key('GET', self.URL, headers={'User-Agent': 'x/1.0'}),
        )


class RecordReplayEndToEndTests(_TempCassetteMixin, SimpleTestCase):
    """通过真正的入口 `request_with_resilience` 走一遍，而不是只测内部函数。"""

    URL = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/property/MolecularFormula/JSON'

    def test_off_mode_does_not_touch_cassette(self):
        os.environ.pop(http_cassette.MODE_ENV, None)
        with mock.patch('core.datasource_client.requests.request',
                        return_value=_fake_response()) as m:
            resp = request_with_resilience('GET', self.URL, source='pubchem')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(m.call_count, 1)
        self.assertEqual(self._read_lines('pubchem'), [], 'off 模式不该写任何 cassette')

    def test_record_writes_cassette(self):
        self._set_mode('record')
        body = b'{"PropertyTable":{"Properties":[{"MolecularFormula":"C9H8O4"}]}}'
        with mock.patch('core.datasource_client.requests.request',
                        return_value=_fake_response(body=body)):
            request_with_resilience('GET', self.URL, source='pubchem')

        lines = self._read_lines('pubchem')
        self.assertEqual(len(lines), 1)
        rec = lines[0]
        self.assertEqual(rec['status'], 200)
        self.assertEqual(base64.b64decode(rec['body_b64']), body)
        self.assertEqual(rec['method'], 'GET')

    def test_replay_returns_recorded_bytes_without_network(self):
        self._set_mode('record')
        body = b'{"MolecularFormula":"C9H8O4"}'
        with mock.patch('core.datasource_client.requests.request',
                        return_value=_fake_response(body=body)):
            request_with_resilience('GET', self.URL, source='pubchem')

        # 切回放，并且**把网络调用打成"一碰就炸"** —— 证明完全没有回源
        self._set_mode('replay')
        with mock.patch('core.datasource_client.requests.request',
                        side_effect=AssertionError('回放模式不该发真实请求')) as m:
            resp = request_with_resilience('GET', self.URL, source='pubchem')

        self.assertEqual(m.call_count, 0, '回放模式必须一次网络调用都没有')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, body, '回放的必须是录制的原始字节')
        self.assertEqual(resp.json()['MolecularFormula'], 'C9H8O4')
        resp.raise_for_status()          # 不应抛（验证 request 已补上）

    def test_replay_miss_raises_instead_of_going_online(self):
        """★ 本模块的安全底线：未命中必须显式失败，绝不静默回源。"""
        self._set_mode('replay')
        with mock.patch('core.datasource_client.requests.request',
                        side_effect=AssertionError('未命中时也不许回源')) as m:
            with self.assertRaises(http_cassette.CassetteMiss) as ctx:
                request_with_resilience('GET', self.URL, source='pubchem')
        self.assertEqual(m.call_count, 0)
        self.assertIn('cassette 未命中', str(ctx.exception))
        self.assertIn('SCIREAGENT_HTTP_MODE=record', str(ctx.exception),
                      '报错必须告诉人怎么录制')

    def test_record_is_idempotent(self):
        """同一请求录第二次不该产生重复行（cassette 是仓库文件，会膨胀）。"""
        self._set_mode('record')
        with mock.patch('core.datasource_client.requests.request',
                        return_value=_fake_response()):
            request_with_resilience('GET', self.URL, source='pubchem')
            request_with_resilience('GET', self.URL, source='pubchem')
        self.assertEqual(len(self._read_lines('pubchem')), 1)

    def test_sources_are_separate_files(self):
        self._set_mode('record')
        with mock.patch('core.datasource_client.requests.request',
                        return_value=_fake_response()):
            request_with_resilience('GET', self.URL, source='pubchem')
            request_with_resilience('GET', 'https://eutils.ncbi.nlm.nih.gov/x',
                                    source='pubmed')
        self.assertEqual(len(self._read_lines('pubchem')), 1)
        self.assertEqual(len(self._read_lines('pubmed')), 1)

    def test_record_stores_final_url_with_params(self):
        """★ 存的必须是 requests **拼好的最终 URL**（含 params），不是调用方传入的。

        实测 PubMed 的调用形如 `request_with_resilience('GET', '.../efetch.fcgi',
        params={'db': 'pubmed', 'id': '24151172'})` —— 传入的 url 只有 `efetch.fcgi`。
        若存传入值，回放的 `resp.url` 就丢了检索条件，任何"从 url 反推参数"的
        下游代码都会拿到错的 URL。
        """
        self._set_mode('record')
        final = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=24151172'
        with mock.patch('core.datasource_client.requests.request',
                        return_value=_fake_response(url=final)):
            request_with_resilience(
                'GET', 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
                source='pubmed', params={'db': 'pubmed', 'id': '24151172'})

        self.assertEqual(self._read_lines('pubmed')[0]['url'], final)

        # 回放出来的 url 也必须是完整地址
        self._set_mode('replay')
        with mock.patch('core.datasource_client.requests.request',
                        side_effect=AssertionError('回放不许回源')):
            resp = request_with_resilience(
                'GET', 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
                source='pubmed', params={'db': 'pubmed', 'id': '24151172'})
        self.assertEqual(resp.url, final)


class HeaderRedactionTests(_TempCassetteMixin, SimpleTestCase):
    """cassette 会进仓库 ⇒ 敏感头不能落盘。"""

    URL = 'https://example.test/secret'

    def test_authorization_and_cookie_never_persisted(self):
        self._set_mode('record')
        resp = _fake_response(headers={
            'Authorization': 'Bearer sk-super-secret',
            'Cookie': 'sessionid=abc123',
            'X-Api-Key': 'sk-1234567890',
            'Content-Type': 'application/json',
            'Retry-After': '7',
        })
        with mock.patch('core.datasource_client.requests.request', return_value=resp):
            request_with_resilience('GET', self.URL, source='pubchem')

        raw = json.dumps(self._read_lines('pubchem'), ensure_ascii=False)
        for leak in ('sk-super-secret', 'sessionid', 'sk-1234567890'):
            self.assertNotIn(leak, raw, f'cassette 落盘了敏感值：{leak}')

        rec = self._read_lines('pubchem')[0]
        self.assertEqual(rec['headers'].get('content-type'), 'application/json')
        self.assertEqual(rec['headers'].get('retry-after'), '7',
                         'retry-after 要保留 —— 容错逻辑（退避阶梯）需要它')

    def test_oversized_body_is_skipped_entirely(self):
        """超过上限**整条不录**。存半截数据会让回放"成功"但内容残缺，比 miss 更危险。"""
        self._set_mode('record')
        huge = b'x' * (http_cassette.MAX_BODY_BYTES + 1)
        with mock.patch('core.datasource_client.requests.request',
                        return_value=_fake_response(body=huge)):
            with self.assertLogs('core.http_cassette', level='WARNING'):
                resp = request_with_resilience('GET', self.URL, source='pubchem')
        self.assertEqual(resp.status_code, 200, '录制跳过不该影响真实请求的返回')
        self.assertEqual(self._read_lines('pubchem'), [],
                         '超大 body 必须整条跳过，不能存截断版')


class RetryableStatusInReplayTests(_TempCassetteMixin, SimpleTestCase):
    """回放 503 时应与真实请求一致：抛 RetryableHttpError 走重试，而不是当成功返回。"""

    URL = 'https://example.test/flaky'

    def test_replayed_503_is_still_retryable(self):
        self._set_mode('record')
        with mock.patch('core.datasource_client.requests.request',
                        return_value=_fake_response(status=503)):
            with self.assertRaises(Exception):
                request_with_resilience('GET', self.URL, source='pubchem', retries=1)

        self._set_mode('replay')
        with mock.patch('core.datasource_client.requests.request',
                        side_effect=AssertionError('回放不许回源')):
            with self.assertRaises(Exception) as ctx:
                request_with_resilience('GET', self.URL, source='pubchem', retries=1)
        self.assertIn('503', str(ctx.exception))
